# backend/cors_config.py
# Simple CORS configuration for Bitcoin Options Platform

from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)

def setup_cors(app):
    """Setup simple CORS middleware."""
    
    logger.info("Setting up CORS middleware with wildcard origins")
    
    # Add CORS middleware - MUST be first middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Temporary fix - allows all domains
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False  # Required when using "*"
    )
    
    logger.info("✅ CORS middleware configured successfully") 