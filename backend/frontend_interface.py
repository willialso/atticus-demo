# backend/frontend_interface.py
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import json
import asyncio
import time

from backend.api import app, ws_manager  # Import from existing API
from backend.utils import setup_logger

logger = setup_logger(__name__)

# Additional Pydantic models for frontend integration
class AdvancedTradeRequest(BaseModel):
    user_id: str
    option_type: str  # "call" or "put"
    strike: float
    expiry_minutes: int
    quantity: int
    side: str = "buy"
    order_type: str = "market"  # "market" or "limit"
    limit_price: Optional[float] = None

class PortfolioAnalysisRequest(BaseModel):
    user_id: str
    analysis_type: str  # "risk", "performance", "greeks"
    timeframe: Optional[str] = "24h"

class MarketDataRequest(BaseModel):
    data_type: str  # "option_chains", "volatility", "sentiment", "regime"
    parameters: Optional[Dict] = None

# Extended API endpoints for advanced frontend integration
@app.get("/market/volatility-surface")
async def get_volatility_surface():
    """Get volatility surface data for all expiries and strikes."""
    try:
        pricing_engine = getattr(app.state, 'pricing_engine', None)
        if not pricing_engine:
            raise HTTPException(status_code=503, detail="Pricing engine not available")
        
        # Get volatility metrics with error handling
        try:
            vol_metrics = pricing_engine.vol_engine.get_volatility_metrics()
        except Exception as e:
            logger.error(f"Error getting volatility metrics: {e}")
            vol_metrics = {
                "current_volatility": 0.0,
                "historical_volatility": 0.0,
                "implied_volatility": 0.0
            }
        
        # Get all option chains with error handling
        try:
            all_chains = pricing_engine.generate_all_chains()
        except Exception as e:
            logger.error(f"Error generating option chains: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate option chains")
        
        # Process the chains with null checks
        surface_data = {}
        for expiry_minutes, chain in all_chains.items():
            if not chain:
                continue
                
            surface_data[str(expiry_minutes)] = {
                "volatility_used": getattr(chain, 'volatility_used', 0.0),
                "strikes_and_ivs": []
            }
            
            # Process calls and puts with null checks
            for option in (chain.calls or []) + (chain.puts or []):
                if not option:
                    continue
                    
                surface_data[str(expiry_minutes)]["strikes_and_ivs"].append({
                    "strike": getattr(option, 'strike', 0.0),
                    "implied_vol": getattr(option, 'implied_vol', 0.0),
                    "option_type": getattr(option, 'option_type', 'unknown'),
                    "moneyness": getattr(option, 'moneyness', 0.0)
                })
        
        return {
            "volatility_metrics": vol_metrics,
            "volatility_surface": surface_data,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Volatility surface error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate volatility surface: {str(e)}")

@app.get("/market/sentiment")
async def get_market_sentiment():
    """Get current market sentiment analysis."""
    try:
        # This would connect to your sentiment analyzer
        # For now, return mock data structure
        sentiment_data = {
            "overall_sentiment": 0.2,  # -1 to 1
            "news_sentiment": 0.3,
            "social_sentiment": 0.1,
            "fear_greed_index": 0.15,
            "confidence": 0.7,
            "key_events": [
                "Bitcoin ETF approval discussions",
                "Federal Reserve interest rate decision pending"
            ],
            "sentiment_trend": {
                "1h": 0.1,
                "4h": 0.05,
                "24h": -0.2
            },
            "timestamp": time.time()
        }
        
        return sentiment_data
        
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/market/regime")
async def get_market_regime():
    """Get current market regime detection."""
    try:
        # This would connect to your regime detector
        regime_data = {
            "current_regime": {
                "regime": 1,
                "regime_name": "High Volatility Bull",
                "confidence": 0.75,
                "probabilities": [0.1, 0.75, 0.05, 0.05, 0.05]
            },
            "regime_statistics": {
                "regime_distribution": {
                    "0": {"percentage": 15, "name": "Low Volatility Bull"},
                    "1": {"percentage": 45, "name": "High Volatility Bull"},
                    "2": {"percentage": 20, "name": "Low Volatility Bear"},
                    "3": {"percentage": 15, "name": "High Volatility Bear"},
                    "4": {"percentage": 5, "name": "Sideways/Consolidation"}
                }
            },
            "transition_probabilities": [
                [0.7, 0.2, 0.05, 0.03, 0.02],
                [0.3, 0.6, 0.05, 0.03, 0.02],
                [0.05, 0.05, 0.7, 0.15, 0.05],
                [0.03, 0.05, 0.2, 0.67, 0.05],
                [0.2, 0.2, 0.2, 0.2, 0.2]
            ],
            "timestamp": time.time()
        }
        
        return regime_data
        
    except Exception as e:
        logger.error(f"Regime detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trades/advanced")
async def execute_advanced_trade(request: AdvancedTradeRequest):
    """Execute advanced trade with additional options."""
    if not trade_executor:
        raise HTTPException(status_code=503, detail="Trade executor not available")
    
    # This would use your enhanced trade execution logic
    # For now, delegate to existing endpoint
    from backend.api import TradeRequest
    
    basic_request = TradeRequest(
        user_id=request.user_id,
        option_type=request.option_type,
        strike=request.strike,
        expiry_minutes=request.expiry_minutes,
        quantity=request.quantity,
        side=request.side
    )
    
    # You can add limit order logic here in the future
    return await execute_trade(basic_request)

@app.get("/users/{user_id}/portfolio/analysis")
async def get_portfolio_analysis(user_id: str, analysis_type: str = "risk"):
    """Get detailed portfolio analysis."""
    try:
        trade_executor = getattr(app.state, 'trade_executor', None)
        if not trade_executor:
            raise HTTPException(status_code=503, detail="Trade executor not available")
        
        # Validate analysis type
        valid_analysis_types = ["risk", "performance", "greeks"]
        if analysis_type not in valid_analysis_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid analysis type. Must be one of: {', '.join(valid_analysis_types)}"
            )
        
        # Get portfolio data with error handling
        try:
            portfolio = trade_executor.get_user_portfolio_summary(user_id)
            if not portfolio:
                raise HTTPException(status_code=404, detail=f"Portfolio not found for user {user_id}")
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve portfolio data")
        
        # Calculate analysis based on type
        try:
            if analysis_type == "risk":
                analysis = calculate_risk_metrics(portfolio)
            elif analysis_type == "performance":
                analysis = calculate_performance_metrics(portfolio)
            else:  # greeks
                analysis = calculate_greek_metrics(portfolio)
        except Exception as e:
            logger.error(f"Error calculating {analysis_type} metrics: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to calculate {analysis_type} metrics")
        
        return {
            "user_id": user_id,
            "analysis_type": analysis_type,
            "analysis": analysis,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portfolio analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def calculate_risk_metrics(portfolio):
    """Calculate risk metrics for the portfolio."""
    try:
        active_positions = portfolio.get("active_positions", [])
        return {
            "net_delta": sum(pos.get("current_delta", 0) for pos in active_positions),
            "total_exposure": portfolio.get("portfolio_value_usd", 0),
            "var_95": calculate_var_95(portfolio),
            "max_loss": sum(pos.get("entry_price", 0) * pos.get("quantity", 0) for pos in active_positions),
            "risk_score": calculate_risk_score(portfolio)
        }
    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        return {
            "net_delta": 0,
            "total_exposure": 0,
            "var_95": 0,
            "max_loss": 0,
            "risk_score": "Unknown"
        }

def calculate_performance_metrics(portfolio):
    """Calculate performance metrics for the portfolio."""
    try:
        return {
            "total_return": portfolio.get("total_realized_pnl", 0),
            "roi": calculate_roi(portfolio),
            "sharpe_ratio": calculate_sharpe_ratio(portfolio),
            "win_rate": calculate_win_rate(portfolio),
            "avg_trade_duration": calculate_avg_trade_duration(portfolio)
        }
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        return {
            "total_return": 0,
            "roi": 0,
            "sharpe_ratio": 0,
            "win_rate": 0,
            "avg_trade_duration": "Unknown"
        }

def calculate_greek_metrics(portfolio):
    """Calculate Greek metrics for the portfolio."""
    try:
        active_positions = portfolio.get("active_positions", [])
        return {
            "total_delta": sum(pos.get("current_delta", 0) for pos in active_positions),
            "total_gamma": sum(pos.get("current_gamma", 0) for pos in active_positions),
            "total_theta": sum(pos.get("current_theta", 0) for pos in active_positions),
            "total_vega": sum(pos.get("current_vega", 0) for pos in active_positions),
            "delta_hedging_recommendation": calculate_delta_hedging_recommendation(portfolio)
        }
    except Exception as e:
        logger.error(f"Error calculating Greek metrics: {e}")
        return {
            "total_delta": 0,
            "total_gamma": 0,
            "total_theta": 0,
            "total_vega": 0,
            "delta_hedging_recommendation": "Unknown"
        }

# Helper functions for metric calculations
def calculate_var_95(portfolio):
    """Calculate Value at Risk at 95% confidence level."""
    # Implementation would go here
    return 0

def calculate_risk_score(portfolio):
    """Calculate risk score based on portfolio composition."""
    # Implementation would go here
    return "Medium"

def calculate_roi(portfolio):
    """Calculate Return on Investment."""
    # Implementation would go here
    return 0

def calculate_sharpe_ratio(portfolio):
    """Calculate Sharpe ratio."""
    # Implementation would go here
    return 0

def calculate_win_rate(portfolio):
    """Calculate win rate from trade history."""
    # Implementation would go here
    return 0

def calculate_avg_trade_duration(portfolio):
    """Calculate average trade duration."""
    # Implementation would go here
    return "15 minutes"

def calculate_delta_hedging_recommendation(portfolio):
    """Calculate delta hedging recommendation."""
    # Implementation would go here
    return "Neutral"

@app.get("/platform/system-status")
async def get_system_status():
    """Get comprehensive system status."""
    try:
        status = {
            "system": {
                "status": "operational",
                "uptime": time.time(),  # Would track actual uptime
                "version": "2.0.0"
            },
            "data_feeds": data_feed_manager.get_exchange_status() if data_feed_manager else {},
            "pricing_engine": {
                "status": "active" if pricing_engine else "inactive",
                "current_btc_price": pricing_engine.current_price if pricing_engine else 0,
                "volatility": pricing_engine.vol_engine.get_volatility_metrics().__dict__ if pricing_engine else {}
            },
            "hedging": {
                "status": "active" if hedger else "inactive",
                "platform_risk": hedger.get_risk_summary() if hedger else {}
            },
            "machine_learning": {
                "volatility_model": {
                    "trained": hasattr(pricing_engine.vol_engine, 'models') if pricing_engine else False,
                    "feature_count": len(getattr(pricing_engine.vol_engine, 'feature_history', [])) if pricing_engine else 0
                },
                "regime_detection": {
                    "models_trained": 0,  # Would check regime detector
                    "current_regime": "Unknown"
                }
            },
            "timestamp": time.time()
        }
        
        return status
        
    except Exception as e:
        logger.error(f"System status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Enhanced WebSocket for real-time data
@app.websocket("/ws/advanced")
async def advanced_websocket_endpoint(websocket: WebSocket):
    """Advanced WebSocket endpoint with subscription management."""
    await ws_manager.connect(websocket)
    
    try:
        # Send initial system status
        await websocket.send_text(json.dumps({
            "type": "system_status",
            "data": await get_system_status()
        }))
        
        # Handle client messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "subscribe":
                # Handle subscriptions
                subscription_type = message.get("subscription")
                
                if subscription_type == "volatility_surface":
                    surface_data = await get_volatility_surface()
                    await websocket.send_text(json.dumps({
                        "type": "volatility_surface",
                        "data": surface_data
                    }))
                
                elif subscription_type == "sentiment":
                    sentiment_data = await get_market_sentiment()
                    await websocket.send_text(json.dumps({
                        "type": "sentiment",
                        "data": sentiment_data
                    }))
                
                elif subscription_type == "regime":
                    regime_data = await get_market_regime()
                    await websocket.send_text(json.dumps({
                        "type": "regime",
                        "data": regime_data
                    }))
            
            elif message.get("type") == "portfolio_subscribe":
                user_id = message.get("user_id")
                if user_id:
                    portfolio = trade_executor.get_user_portfolio_summary(user_id)
                    await websocket.send_text(json.dumps({
                        "type": "portfolio_update",
                        "data": portfolio
                    }))
                    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Advanced WebSocket error: {e}")
        ws_manager.disconnect(websocket)

# Export additional configuration for frontend
@app.get("/config/frontend")
async def get_frontend_config():
    """Get configuration data needed by frontend."""
    return {
        "available_expiries": config.AVAILABLE_EXPIRIES_MINUTES,
        "expiry_labels": config.EXPIRY_LABELS,
        "standard_contract_size": config.STANDARD_CONTRACT_SIZE_BTC,
        "risk_free_rate": config.RISK_FREE_RATE,
        "platform_limits": {
            "min_volatility": config.MIN_VOLATILITY,
            "max_volatility": config.MAX_VOLATILITY,
            "max_single_user_exposure": config.MAX_SINGLE_USER_EXPOSURE_BTC,
            "max_platform_delta": config.MAX_PLATFORM_NET_DELTA_BTC
        },
        "ui_settings": {
            "price_update_interval": config.DATA_BROADCAST_INTERVAL_SECONDS,
            "chart_refresh_rate": 1000,  # milliseconds
            "decimal_places": {
                "btc_price": 2,
                "premium": 4,
                "percentage": 2
            }
        }
    }
