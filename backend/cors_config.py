# backend/cors_config.py
# Bullet-proof CORS configuration for Golden Retriever 2.0

from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://preview--turbo-options-platform.lovable.app",
    "https://turbo-options-platform.lovable.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000"
]

def setup_cors(app):
    """Setup bullet-proof CORS middleware."""
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Add CORS error handling middleware
    app.add_middleware(CORSErrorMiddleware)

class CORSErrorMiddleware(BaseHTTPMiddleware):
    """Middleware to handle CORS errors gracefully."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            resp = await call_next(request)
            
            # Add CORS header if missing
            if "access-control-allow-origin" not in resp.headers:
                origin = request.headers.get("origin")
                if origin in ALLOWED_ORIGINS:
                    resp.headers["Access-Control-Allow-Origin"] = origin
                else:
                    resp.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS[0]
            
            return resp
            
        except Exception as e:
            logger.error(f"CORS error in {request.url}: {e}")
            
            # Check if it's a CORS-related error
            if "cors" in str(e).lower() or "cross-origin" in str(e).lower():
                origin = request.headers.get("origin", ALLOWED_ORIGINS[0])
                return Response(
                    content="CORS error: check backend allowed_origins",
                    status_code=403,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "*",
                        "Content-Type": "application/json"
                    },
                )
            raise 