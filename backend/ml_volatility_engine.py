# backend/ml_volatility_engine.py
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
import joblib
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

from backend.volatility_engine import AdvancedVolatilityEngine
from backend import config
from backend.utils import setup_logger

logger = setup_logger(__name__)

class MLVolatilityEngine(AdvancedVolatilityEngine):
    """Advanced ML-enhanced volatility prediction engine."""
    
    def __init__(self):
        super().__init__()
        self.models = {
            'short_term': None,  # 5-15 min volatility
            'medium_term': None,  # 1-4 hr volatility  
            'regime': None       # Volatility regime classification
        }
        self.scalers = {
            'features': StandardScaler(),
            'target': StandardScaler()
        }
        self.feature_history = []
        self.training_data = pd.DataFrame()
        self.last_retrain = 0
        
    def extract_features(self, lookback_periods: int = 100) -> Optional[np.ndarray]:
        """Extract ML features from price history."""
        if len(self.return_history) < lookback_periods:
            return None
            
        returns = np.array(self.return_history[-lookback_periods:])
        prices = np.array(self.price_history[-lookback_periods:])
        
        features = []
        
        # Price-based features
        features.extend([
            np.mean(returns[-20:]),      # 20-period return mean
            np.std(returns[-20:]),       # 20-period volatility
            np.mean(returns[-10:]),      # 10-period return mean
            np.std(returns[-10:]),       # 10-period volatility
            np.mean(returns[-5:]),       # 5-period return mean
            np.std(returns[-5:]),        # 5-period volatility
        ])
        
        # Momentum features
        if len(returns) >= 20:
            features.extend([
                returns[-1],                           # Last return
                np.mean(returns[-5:]) - np.mean(returns[-20:]),  # Short vs long momentum
                (prices[-1] - prices[-20]) / prices[-20],        # 20-period price change
                (prices[-1] - prices[-10]) / prices[-10],        # 10-period price change
            ])
        else:
            features.extend([0, 0, 0, 0])
            
        # Volatility regime features
        if len(returns) >= 50:
            rolling_vol_20 = pd.Series(returns).rolling(20).std()
            rolling_vol_50 = pd.Series(returns).rolling(50).std()
            features.extend([
                rolling_vol_20.iloc[-1] / rolling_vol_50.iloc[-1] if rolling_vol_50.iloc[-1] > 0 else 1,
                np.percentile(rolling_vol_20.dropna(), 75),  # 75th percentile vol
                np.percentile(rolling_vol_20.dropna(), 25),  # 25th percentile vol
            ])
        else:
            features.extend([1, 0, 0])
            
        # Autocorrelation features
        if len(returns) >= 30:
            features.extend([
                np.corrcoef(returns[-30:-15], returns[-15:])[0,1] if len(returns) >= 30 else 0,  # Lag correlation
                np.corrcoef(returns[-20:-10], returns[-10:])[0,1] if len(returns) >= 20 else 0,   # Shorter lag
            ])
        else:
            features.extend([0, 0])
            
        # Trend features
        if len(prices) >= 20:
            # Linear trend strength
            x = np.arange(20)
            trend_coef = np.polyfit(x, prices[-20:], 1)[0]
            features.append(trend_coef / prices[-1])  # Normalized trend
            
            # Price position in recent range
            recent_high = np.max(prices[-20:])
            recent_low = np.min(prices[-20:])
            if recent_high > recent_low:
                features.append((prices[-1] - recent_low) / (recent_high - recent_low))
            else:
                features.append(0.5)
        else:
            features.extend([0, 0.5])
            
        # Market microstructure proxies
        if len(returns) >= 10:
            features.extend([
                np.sum(np.abs(np.diff(returns[-10:]))) / 10,  # Return roughness
                len([r for r in returns[-10:] if abs(r) > 2*np.std(returns)]) / 10,  # Outlier ratio
            ])
        else:
            features.extend([0, 0])
            
        return np.array(features)
    
    def build_training_dataset(self, min_samples: int = 500) -> bool:
        """Build training dataset from historical features."""
        if len(self.feature_history) < min_samples:
            return False
            
        # Convert to DataFrame
        features_df = pd.DataFrame(self.feature_history)
        
        # Create targets (future volatility)
        targets = {
            'vol_5min': [],   # 5-minute forward volatility
            'vol_15min': [],  # 15-minute forward volatility
            'vol_60min': [],  # 60-minute forward volatility
            'regime': []      # Volatility regime (0=low, 1=medium, 2=high)
        }
        
        # Calculate forward-looking volatilities
        lookforward = {'vol_5min': 5, 'vol_15min': 15, 'vol_60min': 60}
        
        for i in range(len(features_df) - 60):  # Leave 60 periods for forward-looking
            for target_name, periods in lookforward.items():
                end_idx = min(i + periods, len(self.return_history))
                if end_idx > i:
                    future_returns = self.return_history[i:end_idx]
                    if len(future_returns) > 1:
                        targets[target_name].append(np.std(future_returns))
                    else:
                        targets[target_name].append(targets[target_name][-1] if targets[target_name] else 0)
                else:
                    targets[target_name].append(targets[target_name][-1] if targets[target_name] else 0)
            
            # Volatility regime classification
            current_vol = targets['vol_15min'][-1] if targets['vol_15min'] else 0
            if i >= 100:  # Need history for regime classification
                recent_vols = [targets['vol_15min'][j] for j in range(max(0, i-100), i)]
                if recent_vols:
                    vol_75th = np.percentile(recent_vols, 75)
                    vol_25th = np.percentile(recent_vols, 25)
                    
                    if current_vol > vol_75th:
                        targets['regime'].append(2)  # High vol regime
                    elif current_vol < vol_25th:
                        targets['regime'].append(0)  # Low vol regime
                    else:
                        targets['regime'].append(1)  # Medium vol regime
                else:
                    targets['regime'].append(1)
            else:
                targets['regime'].append(1)
        
        # Trim features to match targets
        features_trimmed = features_df.iloc[:len(targets['vol_5min'])]
        
        # Create training DataFrame
        self.training_data = features_trimmed.copy()
        for target_name, target_values in targets.items():
            self.training_data[target_name] = target_values
            
        return True
    
    def train_models(self) -> bool:
        """Train ML models for volatility prediction."""
        if self.training_data.empty:
            if not self.build_training_dataset():
                logger.warning("Insufficient data for ML training")
                return False
                
        logger.info(f"Training ML models with {len(self.training_data)} samples")
        
        # Prepare features and targets
        feature_cols = [col for col in self.training_data.columns 
                       if col not in ['vol_5min', 'vol_15min', 'vol_60min', 'regime']]
        X = self.training_data[feature_cols].fillna(0)
        
        # Scale features
        X_scaled = self.scalers['features'].fit_transform(X)
        
        # Time series split for validation
        tscv = TimeSeriesSplit(n_splits=3)
        
        try:
            # Train short-term volatility model (5-15 min)
            y_short = self.training_data['vol_15min'].fillna(method='bfill')
            self.models['short_term'] = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
            self.models['short_term'].fit(X_scaled, y_short)
            
            # Train medium-term volatility model (1-4 hr)
            y_medium = self.training_data['vol_60min'].fillna(method='bfill')
            self.models['medium_term'] = RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                random_state=42
            )
            self.models['medium_term'].fit(X_scaled, y_medium)
            
            # Train regime classification model
            from sklearn.ensemble import RandomForestClassifier
            y_regime = self.training_data['regime'].fillna(1).astype(int)
            self.models['regime'] = RandomForestClassifier(
                n_estimators=100,
                max_depth=6,
                random_state=42
            )
            self.models['regime'].fit(X_scaled, y_regime)
            
            self.last_retrain = len(self.training_data)
            logger.info("ML volatility models trained successfully")
            return True
            
        except Exception as e:
            logger.error(f"ML training error: {e}")
            return False
    
    def predict_volatility_ml(self, expiry_minutes: int) -> Optional[float]:
        """Predict volatility using ML models."""
        features = self.extract_features()
        if features is None:
            return None
            
        # Store features for future training
        self.feature_history.append(features.tolist())
        if len(self.feature_history) > 5000:  # Limit memory usage
            self.feature_history = self.feature_history[-5000:]
        
        # Retrain periodically
        if (len(self.feature_history) % 100 == 0 and 
            len(self.feature_history) > self.last_retrain + 200):
            self.train_models()
        
        # Use appropriate model based on expiry
        model_key = 'short_term' if expiry_minutes <= 60 else 'medium_term'
        model = self.models[model_key]
        
        if model is None:
            return self.get_expiry_adjusted_volatility(expiry_minutes)  # Fallback
            
        try:
            # Scale features
            features_scaled = self.scalers['features'].transform(features.reshape(1, -1))
            
            # Predict
            predicted_vol = model.predict(features_scaled)[0]
            
            # Get regime prediction for adjustment
            if self.models['regime'] is not None:
                regime_pred = self.models['regime'].predict(features_scaled)[0]
                regime_multipliers = {0: 0.8, 1: 1.0, 2: 1.3}  # Low, medium, high vol regimes
                predicted_vol *= regime_multipliers.get(regime_pred, 1.0)
            
            # Apply bounds
            predicted_vol = max(min(predicted_vol, config.MAX_VOLATILITY), config.MIN_VOLATILITY)
            
            # Blend with traditional calculation for robustness
            traditional_vol = self.get_expiry_adjusted_volatility(expiry_minutes)
            final_vol = 0.7 * predicted_vol + 0.3 * traditional_vol
            
            return final_vol
            
        except Exception as e:
            logger.error(f"ML volatility prediction error: {e}")
            return self.get_expiry_adjusted_volatility(expiry_minutes)  # Fallback
    
    def get_expiry_adjusted_volatility(self, expiry_minutes: int) -> float:
        """Override parent method to use ML predictions when available."""
        ml_vol = self.predict_volatility_ml(expiry_minutes)
        if ml_vol is not None:
            return ml_vol
        else:
            return super().get_expiry_adjusted_volatility(expiry_minutes)
    
    def get_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """Get feature importance from trained models."""
        importance = {}
        
        feature_names = [
            'return_mean_20', 'vol_20', 'return_mean_10', 'vol_10', 'return_mean_5', 'vol_5',
            'last_return', 'momentum_diff', 'price_change_20', 'price_change_10',
            'vol_ratio', 'vol_75th', 'vol_25th', 'lag_corr_30', 'lag_corr_20',
            'trend_coef', 'price_position', 'return_roughness', 'outlier_ratio'
        ]
        
        for model_name, model in self.models.items():
            if model is not None and hasattr(model, 'feature_importances_'):
                importance[model_name] = dict(zip(feature_names, model.feature_importances_))
                
        return importance
