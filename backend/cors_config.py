# backend/cors_config.py
# Bullet-proof CORS configuration for Golden Retriever 2.0

from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://preview--turbo-options-platform.lovable.app",
    "https://turbo-options-platform.lovable.app",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",  # Vite default
    "http://localhost:8080",  # Alternative dev port
    "http://localhost:8000"
]

def setup_cors(app):
    """Setup bullet-proof CORS middleware."""
    
    logger.info(f"Setting up CORS middleware with origins: {ALLOWED_ORIGINS}")
    
    # Add CORS middleware - MUST be first middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "*",
            "Content-Type",
            "Authorization",
            "X-User-ID",
            "X-Requested-With",
            "Accept",
            "Origin",
            "Access-Control-Request-Method",
            "Access-Control-Request-Headers"
        ],
        expose_headers=[
            "*",
            "Content-Type",
            "X-User-ID",
            "X-Request-ID"
        ],
        max_age=86400  # Cache preflight for 24 hours
    )
    
    # Add CORS error handling middleware
    app.add_middleware(CORSErrorMiddleware)
    
    logger.info("✅ CORS middleware configured successfully")

class CORSErrorMiddleware(BaseHTTPMiddleware):
    """Middleware to handle CORS errors gracefully."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Handle preflight OPTIONS requests
            if request.method == "OPTIONS":
                origin = request.headers.get("origin", ALLOWED_ORIGINS[0])
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
                if origin in ALLOWED_ORIGINS:
                    resp.headers["Access-Control-Allow-Origin"] = origin
                else:
                    resp.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS[0]
                
                # Add other CORS headers
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                resp.headers["Access-Control-Allow-Headers"] = "*"
            
            return resp
            
        except Exception as e:
            logger.error(f"CORS error in {request.method} {request.url}: {e}")
            
            # Check if it's a CORS-related error
            if "cors" in str(e).lower() or "cross-origin" in str(e).lower():
                origin = request.headers.get("origin", ALLOWED_ORIGINS[0])
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