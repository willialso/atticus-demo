# backend/api_gr2.py
# Golden Retriever 2.0 FastAPI Integration

import sys
import os
import logging
from typing import Dict, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from pydantic import BaseModel, ValidationError, Field
import json
from uuid import uuid4

# Add the project root to Python path to import gr2
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from gr2.screen_rag import GR2
    from gr2.config import SCREEN_SCHEMA, SYSTEM_PROMPT
    from gr2.post_processor import polish, clear_user_cache, get_cache_stats
    from gr2.kb_growth import kb_tracker
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

async def get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    """Extract user ID from header or generate one."""
    return x_user_id or str(uuid4())

@router.post("/gr2/chat")
async def chat_endpoint(req: ChatRequest, request: Request, user_id: str = Depends(get_user_id)):
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
        
        # Process with Golden Retriever 2.0
        result = GR2(
            question=req.message,
            screen_state=screen_state
        )
        
        # Log missed questions for KB improvement
        if result.confidence < 0.3 or len(result.retrieved_docs) < 1:
            screen_context = f"BTC:${screen_state.get('current_btc_price', 0):,.0f}, {screen_state.get('selected_option_type', 'none')} option"
            kb_tracker.log_miss(
                question=req.message,
                confidence=result.confidence,
                retrieved_docs_count=len(result.retrieved_docs),
                user_id=user_id,
                screen_context=screen_context
            )
        
        # Apply post-processing for clean, friendly output
        final_answer = polish(user_id, result.answer, req.message)
        
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
        final_fallback = polish(user_id, fallback_answer, req.message)
        return ChatResponse(
            answer=final_fallback,
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

@router.get("/gr2/kb-growth")
async def get_kb_growth_stats():
    """Get knowledge base growth statistics and improvement suggestions."""
    if not GR2_AVAILABLE:
        raise HTTPException(status_code=503, detail="Golden Retriever 2.0 not available")
    
    try:
        misses_summary = kb_tracker.get_misses_summary(days=30)
        suggestions = kb_tracker.suggest_kb_improvements()
        
        return {
            "misses_summary": misses_summary,
            "improvement_suggestions": suggestions,
            "total_suggestions": len(suggestions)
        }
    except Exception as e:
        logger.error(f"Error getting KB growth stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving KB growth statistics")

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
        
        # Apply post-processing
        user_id = req.user_id or "test_user"
        final_answer = polish(user_id, result.answer, "What does Delta mean?")
        
        return {
            "test_passed": True,
            "test_question": "What does Delta mean?",
            "test_result": {
                "answer": final_answer[:100] + "..." if len(final_answer) > 100 else final_answer,
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
        return get_cache_stats()
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving cache statistics")

@router.post("/gr2/clear-cache")
async def clear_cache(user_id: Optional[str] = None):
    """Clear the cache for a specific user or all users."""
    if not GR2_AVAILABLE:
        raise HTTPException(status_code=503, detail="Golden Retriever 2.0 not available")
    
    try:
        if user_id:
            clear_user_cache(user_id)
            return {"message": f"Cache cleared for user {user_id}"}
        else:
            # Clear all caches
            from gr2.post_processor import CACHE
            CACHE.clear()
            return {"message": "All caches cleared"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Error clearing cache")

@router.get("/gr2/analogies")
async def get_available_analogies():
    """Get available analogies for debugging."""
    if not GR2_AVAILABLE:
        raise HTTPException(status_code=503, detail="Golden Retriever 2.0 not available")
    
    try:
        import json
        with open('gr2/analogies.json', 'r') as f:
            analogies = json.load(f)
        return {
            "analogies": analogies,
            "count": len(analogies)
        }
    except Exception as e:
        logger.error(f"Error retrieving analogies: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving analogies") 