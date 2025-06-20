# backend/cors_config.py
# Simple CORS configuration for Bitcoin Options Platform

from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)

def is_lovable_domain(origin: str) -> bool:
    """Check if origin is a Lovable domain (allows any *.lovable.app or *.lovableproject.com)"""
    return (origin.endswith('.lovable.app') or 
            origin.endswith('.lovable.com') or 
            origin.endswith('.lovableproject.com'))

def setup_cors(app):
    """Setup CORS middleware with dynamic Lovable domain support."""
    
    logger.info("Setting up CORS middleware with dynamic Lovable domain support")
    
    # Add CORS middleware - MUST be first middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins - we'll handle Lovable domains dynamically
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,  # Required when using "*"
        allow_origin_regex=r"https://.*\.lovableproject\.com|https://.*\.lovable\.app|https://.*\.lovable\.com"  # Regex for Lovable domains
    )
    
    logger.info("✅ CORS middleware configured with dynamic Lovable domain support") 