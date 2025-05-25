# backend/regime_detector.py
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from hmmlearn import hmm
from scipy import stats
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

from backend import config
from backend.utils import setup_logger

logger = setup_logger(__name__)

class MarketRegimeDetector:
    """Advanced market regime detection using multiple algorithms."""
    
    def __init__(self):
        self.price_history = []
        self.return_history = []
        self.volume_history = []
        self.regime_history = []
        
        # Models
        self.hmm_model = None
        self.gmm_model = None
        self.kmeans_model = None
        self.scaler = StandardScaler()
        
        # Regime definitions
        self.regime_names = {
            0: "Low Volatility Bull",
            1: "High Volatility Bull", 
            2: "Low Volatility Bear",
            3: "High Volatility Bear",
            4: "Sideways/Consolidation"
        }
        
        self.last_regime = 4  # Start with sideways
        self.regime_probabilities = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
        
    def update_data(self, price: float, volume: float = 0) -> None:
        """Update with new market data."""
        self.price_history.append(price)
        self.volume_history.append(volume)
        
        # Calculate returns
        if len(self.price_history) >= 2:
            ret = np.log(price / self.price_history[-2])
            self.return_history.append(ret)
        
        # Limit history size
        max_size = 5000
        if len(self.price_history) > max_size:
            self.price_history = self.price_history[-max_size:]
            self.return_history = self.return_history[-max_size:]
            self.volume_history = self.volume_history[-max_size:]
            
    def extract_regime_features(self, lookback: int = 100) -> Optional[np.ndarray]:
        """Extract features for regime detection."""
        if len(self.return_history) < lookback:
            return None
            
        returns = np.array(self.return_history[-lookback:])
        prices = np.array(self.price_history[-lookback:])
        volumes = np.array(self.volume_history[-lookback:])
        
        features = []
        
        # Volatility features (multiple timeframes)
        for window in [5, 10, 20, 50]:
            if len(returns) >= window:
                vol = pd.Series(returns).rolling(window).std().iloc[-1]
                features.append(vol if not np.isnan(vol) else 0)
            else:
                features.append(0)
        
        # Return features
        features.extend([
            np.mean(returns[-20:]) if len(returns) >= 20 else 0,  # Recent return mean
            np.mean(returns[-10:]) if len(returns) >= 10 else 0,  # Short-term return mean
            np.mean(returns[-5:]) if len(returns) >= 5 else 0,    # Very short-term return mean
        ])
        
        # Trend features
        if len(prices) >= 20:
            # Price trends over different periods
            for period in [5, 10, 20]:
                if len(prices) >= period:
                    trend = (prices[-1] - prices[-period]) / prices[-period]
                    features.append(trend)
                else:
                    features.append(0)
        else:
            features.extend([0, 0, 0])
            
        # Momentum features
        if len(returns) >= 20:
            # MACD-like features
            ema_fast = pd.Series(prices).ewm(span=12).mean().iloc[-1]
            ema_slow = pd.Series(prices).ewm(span=26).mean().iloc[-1]
            macd = (ema_fast - ema_slow) / ema_slow
            features.append(macd)
            
            # RSI-like feature
            gains = [r for r in returns[-14:] if r > 0]
            losses = [-r for r in returns[-14:] if r < 0]
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            features.append(rsi / 100 - 0.5)  # Normalize around 0
        else:
            features.extend([0, 0])
            
        # Volume features (if available)
        if len(volumes) >= 20 and np.mean(volumes) > 0:
            # Volume trend
            volume_trend = (volumes[-1] - np.mean(volumes[-20:])) / np.mean(volumes[-20:])
            features.append(volume_trend)
            
            # Volume volatility
            volume_vol = np.std(volumes[-20:]) / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 0
            features.append(volume_vol)
        else:
            features.extend([0, 0])
            
        # Market microstructure features
        if len(returns) >= 50:
            # Hurst exponent (simplified)
            hurst = self._calculate_hurst_exponent(returns[-50:])
            features.append(hurst)
            
            # Kurtosis (tail risk)
            kurtosis = stats.kurtosis(returns[-50:])
            features.append(kurtosis / 10)  # Normalize
            
            # Skewness
            skewness = stats.skew(returns[-50:])
            features.append(skewness)
        else:
            features.extend([0.5, 0, 0])  # Default neutral values
            
        # Autocorrelation features
        if len(returns) >= 30:
            # Lag-1 autocorrelation
            autocorr_1 = np.corrcoef(returns[-30:-1], returns[-29:])[0,1] if len(returns) >= 30 else 0
            features.append(autocorr_1 if not np.isnan(autocorr_1) else 0)
        else:
            features.append(0)
            
        return np.array(features)
    
    def _calculate_hurst_exponent(self, returns: np.ndarray) -> float:
        """Calculate simplified Hurst exponent."""
        try:
            # Rescaled range analysis (simplified)
            n = len(returns)
            if n < 10:
                return 0.5
                
            # Calculate cumulative deviations
            mean_return = np.mean(returns)
            deviations = returns - mean_return
            cumulative_deviations = np.cumsum(deviations)
            
            # Range of cumulative deviations
            R = np.max(cumulative_deviations) - np.min(cumulative_deviations)
            
            # Standard deviation
            S = np.std(returns)
            
            if S == 0:
                return 0.5
                
            # Rescaled range
            rs = R / S
            
            # Hurst exponent approximation
            hurst = np.log(rs) / np.log(n)
            
            return np.clip(hurst, 0, 1)
            
        except Exception:
            return 0.5
    
    def train_hmm_model(self, n_components: int = 5) -> bool:
        """Train Hidden Markov Model for regime detection."""
        if len(self.return_history) < 200:
            logger.warning("Insufficient data for HMM training")
            return False
            
        try:
            # Prepare features
            features_list = []
            for i in range(100, len(self.return_history)):
                features = self.extract_regime_features(100)
                if features is not None:
                    features_list.append(features)
                    
            if len(features_list) < 50:
                return False
                
            features_array = np.array(features_list)
            
            # Scale features
            features_scaled = self.scaler.fit_transform(features_array)
            
            # Train HMM
            self.hmm_model = hmm.GaussianHMM(
                n_components=n_components,
                covariance_type="full",
                n_iter=100,
                random_state=42
            )
            
            self.hmm_model.fit(features_scaled)
            
            logger.info(f"HMM model trained with {n_components} components")
            return True
            
        except Exception as e:
            logger.error(f"HMM training error: {e}")
            return False
    
    def train_gmm_model(self, n_components: int = 5) -> bool:
        """Train Gaussian Mixture Model for regime detection."""
        if len(self.return_history) < 200:
            return False
            
        try:
            # Prepare features (same as HMM)
            features_list = []
            for i in range(100, len(self.return_history)):
                features = self.extract_regime_features(100)
                if features is not None:
                    features_list.append(features)
                    
            if len(features_list) < 50:
                return False
                
            features_array = np.array(features_list)
            features_scaled = self.scaler.fit_transform(features_array)
            
            # Train GMM
            self.gmm_model = GaussianMixture(
                n_components=n_components,
                covariance_type='full',
                random_state=42
            )
            
            self.gmm_model.fit(features_scaled)
            
            logger.info(f"GMM model trained with {n_components} components")
            return True
            
        except Exception as e:
            logger.error(f"GMM training error: {e}")
            return False
    
    def train_kmeans_model(self, n_clusters: int = 5) -> bool:
        """Train K-Means clustering for regime detection."""
        if len(self.return_history) < 200:
            return False
            
        try:
            # Prepare features
            features_list = []
            for i in range(100, len(self.return_history)):
                features = self.extract_regime_features(100)
                if features is not None:
                    features_list.append(features)
                    
            if len(features_list) < 50:
                return False
                
            features_array = np.array(features_list)
            features_scaled = self.scaler.fit_transform(features_array)
            
            # Train K-Means
            self.kmeans_model = KMeans(
                n_clusters=n_clusters,
                random_state=42,
                n_init=10
            )
            
            self.kmeans_model.fit(features_scaled)
            
            logger.info(f"K-Means model trained with {n_clusters} clusters")
            return True
            
        except Exception as e:
            logger.error(f"K-Means training error: {e}")
            return False
    
    def detect_current_regime(self) -> Dict[str, any]:
        """Detect current market regime using all available models."""
        current_features = self.extract_regime_features()
        
        if current_features is None:
            return {
                "regime": self.last_regime,
                "regime_name": self.regime_names[self.last_regime],
                "confidence": 0.2,
                "probabilities": self.regime_probabilities.tolist(),
                "method": "default"
            }
        
        results = {}
        
        # Scale features
        try:
            features_scaled = self.scaler.transform(current_features.reshape(1, -1))
        except:
            return {
                "regime": self.last_regime,
                "regime_name": self.regime_names[self.last_regime],
                "confidence": 0.2,
                "probabilities": self.regime_probabilities.tolist(),
                "method": "scaling_error"
            }
        
        # HMM prediction
        if self.hmm_model is not None:
            try:
                hmm_regime = self.hmm_model.predict(features_scaled)[0]
                hmm_probs = self.hmm_model.predict_proba(features_scaled)[0]
                results['hmm'] = {
                    'regime': int(hmm_regime),
                    'probabilities': hmm_probs.tolist()
                }
            except Exception as e:
                logger.warning(f"HMM prediction error: {e}")
        
        # GMM prediction
        if self.gmm_model is not None:
            try:
                gmm_regime = self.gmm_model.predict(features_scaled)[0]
                gmm_probs = self.gmm_model.predict_proba(features_scaled)[0]
                results['gmm'] = {
                    'regime': int(gmm_regime),
                    'probabilities': gmm_probs.tolist()
                }
            except Exception as e:
                logger.warning(f"GMM prediction error: {e}")
        
        # K-Means prediction
        if self.kmeans_model is not None:
            try:
                kmeans_regime = self.kmeans_model.predict(features_scaled)[0]
                # K-means doesn't give probabilities, so create uniform
                kmeans_probs = np.zeros(5)
                kmeans_probs[kmeans_regime] = 1.0
                results['kmeans'] = {
                    'regime': int(kmeans_regime),
                    'probabilities': kmeans_probs.tolist()
                }
            except Exception as e:
                logger.warning(f"K-Means prediction error: {e}")
        
        # Ensemble prediction
        if results:
            # Average the probabilities from all models
            all_probs = []
            regime_votes = []
            
            for method, result in results.items():
                all_probs.append(result['probabilities'])
                regime_votes.append(result['regime'])
            
            # Average probabilities
            ensemble_probs = np.mean(all_probs, axis=0)
            ensemble_regime = np.argmax(ensemble_probs)
            confidence = ensemble_probs[ensemble_regime]
            
            # Update history
            self.last_regime = ensemble_regime
            self.regime_probabilities = ensemble_probs
            
            regime_result = {
                "regime": int(ensemble_regime),
                "regime_name": self.regime_names[ensemble_regime],
                "confidence": float(confidence),
                "probabilities": ensemble_probs.tolist(),
                "method": "ensemble",
                "individual_results": results
            }
            
            self.regime_history.append(regime_result)
            if len(self.regime_history) > 1000:
                self.regime_history = self.regime_history[-1000:]
                
            return regime_result
        
        else:
            # No models available, use fallback
            return {
                "regime": self.last_regime,
                "regime_name": self.regime_names[self.last_regime],
                "confidence": 0.2,
                "probabilities": self.regime_probabilities.tolist(),
                "method": "fallback"
            }
    
    def get_regime_transition_probabilities(self) -> Optional[np.ndarray]:
        """Get regime transition probability matrix from HMM."""
        if self.hmm_model is not None:
            return self.hmm_model.transmat_
        return None
    
    def get_regime_statistics(self, lookback_hours: int = 24) -> Dict:
        """Get regime statistics over specified period."""
        if not self.regime_history:
            return {}
        
        cutoff_time = len(self.regime_history) - (lookback_hours * 60)  # Assuming minute data
        recent_regimes = self.regime_history[max(0, cutoff_time):]
        
        if not recent_regimes:
            return {}
        
        # Count regime occurrences
        regime_counts = {}
        for regime_result in recent_regimes:
            regime = regime_result['regime']
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        # Calculate regime durations
        regime_durations = {}
        current_regime = None
        current_duration = 0
        
        for regime_result in recent_regimes:
            regime = regime_result['regime']
            if regime == current_regime:
                current_duration += 1
            else:
                if current_regime is not None:
                    if current_regime not in regime_durations:
                        regime_durations[current_regime] = []
                    regime_durations[current_regime].append(current_duration)
                current_regime = regime
                current_duration = 1
        
        # Add final duration
        if current_regime is not None:
            if current_regime not in regime_durations:
                regime_durations[current_regime] = []
            regime_durations[current_regime].append(current_duration)
        
        # Calculate statistics
        stats = {
            "regime_distribution": {
                int(regime): {
                    "count": count,
                    "percentage": count / len(recent_regimes) * 100,
                    "name": self.regime_names.get(regime, f"Regime {regime}")
                }
                for regime, count in regime_counts.items()
            },
            "regime_durations": {
                int(regime): {
                    "average_duration": np.mean(durations),
                    "max_duration": np.max(durations),
                    "min_duration": np.min(durations),
                    "total_periods": len(durations)
                }
                for regime, durations in regime_durations.items()
            },
            "current_regime": recent_regimes[-1] if recent_regimes else None,
            "total_observations": len(recent_regimes)
        }
        
        return stats
