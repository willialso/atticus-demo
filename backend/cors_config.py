# backend/cors_config.py
# Bullet-proof CORS configuration for Bitcoin Options Platform

from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://preview--turbo-options-platform.lovable.app",
    "https://turbo-options-platform.lovable.app",
    "https://id-preview--1a576357-c970-4272-b0e7-38700d4a29d3.lovable.app",  # New Lovable preview domain
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",  # Vite default
    "http://localhost:8080",  # Alternative dev port
    "http://localhost:8000"
]

def is_lovable_domain(origin: str) -> bool:
    """Check if origin is a Lovable domain (allows any *.lovable.app)"""
    return origin.endswith('.lovable.app') or origin.endswith('.lovable.com')

def setup_cors(app):
    """Setup bullet-proof CORS middleware."""
    
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

class CORSErrorMiddleware(BaseHTTPMiddleware):
    """Middleware to handle CORS errors gracefully."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Handle preflight OPTIONS requests
            if request.method == "OPTIONS":
                origin = request.headers.get("origin", "*")
                # Allow any Lovable domain or localhost
                if is_lovable_domain(origin) or origin.startswith("http://localhost") or origin == "*":
                    return Response(
                        content="",
                        status_code=200,
                        headers={
                            "Access-Control-Allow-Origin": origin,
                            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                            "Access-Control-Allow-Headers": "*",
                            "Access-Control-Max-Age": "86400",
                            "Access-Control-Allow-Credentials": "true"
                        }
                    )
            
            resp = await call_next(request)
            
            # Add CORS header if missing
            if "access-control-allow-origin" not in resp.headers:
                origin = request.headers.get("origin")
                # Allow any Lovable domain or localhost
                if is_lovable_domain(origin) or origin.startswith("http://localhost") or origin == "*":
                    resp.headers["Access-Control-Allow-Origin"] = origin
                else:
                    resp.headers["Access-Control-Allow-Origin"] = "*"
                
                # Add other CORS headers
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                resp.headers["Access-Control-Allow-Headers"] = "*"
            
            return resp
            
        except Exception as e:
            logger.error(f"CORS error in {request.method} {request.url}: {e}")
            
            # Check if it's a CORS-related error
            if "cors" in str(e).lower() or "cross-origin" in str(e).lower():
                origin = request.headers.get("origin", "*")
                return Response(
                    content=json.dumps({"error": "CORS error: check backend allowed_origins"}),
                    status_code=403,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Allow-Credentials": "true",
                        "Content-Type": "application/json"
                    },
                )
            raise 