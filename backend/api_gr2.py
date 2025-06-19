# backend/api_gr2.py
# Golden Retriever 2.0 FastAPI Integration

import sys
import os
import logging
from typing import Dict, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError, Field
import json

# Add the project root to Python path to import gr2
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from gr2.screen_rag import GR2
    from gr2.config import SCREEN_SCHEMA
    from gr2.post_processor import clean_response, format_bullet_points
    from gr2.loop_guard import loop_guard
    GR2_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Golden Retriever 2.0 not available: {e}")
    GR2_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter()

class LovableContext(BaseModel):
    screen_state: Dict[str, Any]

class ChatRequest(BaseModel):
    message: str
    screen_state: Optional[Dict[str, Any]] = None  # Original format
    context: Optional[LovableContext] = None  # Lovable format
    user_id: Optional[str] = None  # Lovable format

class ChatResponse(BaseModel):
    answer: str
    sources: Optional[list] = None
    confidence: Optional[float] = None
    jargon_terms: Optional[list] = None
    context_used: Optional[str] = None

@router.post("/gr2/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    """Golden Retriever 2.0 chat endpoint with screen-aware RAG."""
    try:
        if not GR2_AVAILABLE:
            return ChatResponse(
                answer="Golden Retriever 2.0 is not available. Please check the installation.",
                confidence=0.0
            )
        
        # Handle both request formats
        screen_state = None
        if req.screen_state:
            # Original format
            screen_state = req.screen_state
        elif req.context and req.context.screen_state:
            # Lovable format
            screen_state = req.context.screen_state
        else:
            # Default screen state if none provided
            screen_state = {
                "current_btc_price": 0.0,
                "selected_option_type": "",
                "selected_strike": None,
                "selected_expiry": 0,
                "visible_strikes": [],
                "active_tab": ""
            }
        
        # Validate and normalize screen state
        try:
            # Basic validation - ensure required fields exist
            required_fields = ["current_btc_price", "selected_option_type", "selected_strike", 
                             "selected_expiry", "visible_strikes", "active_tab"]
            for field in required_fields:
                if field not in screen_state:
                    screen_state[field] = None if field in ["selected_strike"] else 0.0 if field == "current_btc_price" else [] if field == "visible_strikes" else ""
            
            # Type validation
            if not isinstance(screen_state["current_btc_price"], (int, float)):
                screen_state["current_btc_price"] = 0.0
            if not isinstance(screen_state["visible_strikes"], list):
                screen_state["visible_strikes"] = []
                
        except Exception as e:
            logger.warning(f"Screen state validation error: {e}")
            # Continue with default values
        
        # Check for loops (repetitive questions)
        user_id = req.user_id or "default_user"
        is_loop, loop_response = loop_guard.check_loop(req.message, user_id)
        
        if is_loop:
            return ChatResponse(
                answer=loop_response,
                confidence=1.0,
                sources=[],
                jargon_terms=[],
                context_used="Loop prevention"
            )
        
        # Process with Golden Retriever 2.0
        result = GR2(
            question=req.message,
            screen_state=screen_state
        )
        
        # Post-process the response for user-friendly output
        cleaned_answer = clean_response(result.answer)
        
        # Format as bullet points if response is long
        final_answer = format_bullet_points(cleaned_answer)
        
        return ChatResponse(
            answer=final_answer,
            sources=result.retrieved_docs_titles,
            confidence=result.confidence,
            jargon_terms=result.jargon_terms,
            context_used=result.context_used
        )
        
    except Exception as e:
        logger.error(f"Error in GR2 chat endpoint: {e}", exc_info=True)
        # Return fallback response
        fallback_answer = GR2.fallback(req.message) if GR2_AVAILABLE else "Service temporarily unavailable."
        cleaned_fallback = clean_response(fallback_answer)
        return ChatResponse(
            answer=cleaned_fallback,
            confidence=0.0
        )

@router.get("/gr2/health")
async def gr2_health_check():
    """Health check for Golden Retriever 2.0."""
    return {
        "service": "Golden Retriever 2.0",
        "status": "operational" if GR2_AVAILABLE else "unavailable",
        "version": "2.0.0",
        "available": GR2_AVAILABLE
    }

@router.get("/gr2/knowledge-base")
async def get_knowledge_base():
    """Get the current knowledge base for debugging."""
    if not GR2_AVAILABLE:
        raise HTTPException(status_code=503, detail="Golden Retriever 2.0 not available")
    
    try:
        from gr2.config import BTC_OPTIONS_KB
        return {
            "knowledge_base": BTC_OPTIONS_KB,
            "count": len(BTC_OPTIONS_KB)
        }
    except Exception as e:
        logger.error(f"Error retrieving knowledge base: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving knowledge base")

@router.post("/gr2/test")
async def test_gr2_endpoint(req: ChatRequest):
    """Test endpoint for Golden Retriever 2.0 functionality."""
    try:
        if not GR2_AVAILABLE:
            return {
                "error": "Golden Retriever 2.0 not available",
                "test_passed": False
            }
        
        # Test with sample data
        test_screen_state = {
            "current_btc_price": 105000.0,
            "selected_option_type": "call",
            "selected_strike": 105000.0,
            "selected_expiry": 240,  # 4 hours
            "visible_strikes": [104000, 104500, 105000, 105500, 106000],
            "active_tab": "options_chain"
        }
        
        result = GR2(
            question="What does Delta mean?",
            screen_state=test_screen_state
        )
        
        return {
            "test_passed": True,
            "test_question": "What does Delta mean?",
            "test_result": {
                "answer": result.answer[:100] + "..." if len(result.answer) > 100 else result.answer,
                "confidence": result.confidence,
                "sources": result.retrieved_docs_titles
            }
        }
        
    except Exception as e:
        logger.error(f"Error in GR2 test endpoint: {e}", exc_info=True)
        return {
            "test_passed": False,
            "error": str(e)
        }

@router.get("/gr2/cache-stats")
async def get_cache_stats():
    """Get loop guard cache statistics."""
    if not GR2_AVAILABLE:
        raise HTTPException(status_code=503, detail="Golden Retriever 2.0 not available")
    
    try:
        stats = loop_guard.get_cache_stats()
        return {
            "cache_stats": stats,
            "status": "operational"
        }
    except Exception as e:
        logger.error(f"Error retrieving cache stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving cache stats")

@router.post("/gr2/clear-cache")
async def clear_cache(user_id: Optional[str] = None):
    """Clear loop guard cache for specific user or all users."""
    if not GR2_AVAILABLE:
        raise HTTPException(status_code=503, detail="Golden Retriever 2.0 not available")
    
    try:
        loop_guard.clear_cache(user_id)
        return {
            "message": f"Cache cleared for {'all users' if user_id is None else f'user {user_id}'}",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Error clearing cache")

@router.get("/gr2/analogies")
async def get_available_analogies():
    """Get list of available analogies for debugging."""
    if not GR2_AVAILABLE:
        raise HTTPException(status_code=503, detail="Golden Retriever 2.0 not available")
    
    try:
        from gr2.screen_rag import GR2
        gr2_instance = GR2()
        analogies = list(gr2_instance.analogies.keys())
        return {
            "available_analogies": analogies,
            "count": len(analogies),
            "status": "operational"
        }
    except Exception as e:
        logger.error(f"Error retrieving analogies: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving analogies") 