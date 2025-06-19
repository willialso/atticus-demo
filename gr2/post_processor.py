# gr2/post_processor.py
# Post-processing utilities for Golden Retriever 2.0

import re
import html
import logging
from collections import defaultdict, deque
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Tag cleaning regex
TAG_RE = re.compile(r"\[[A-Z][^]]+?\]")

# Loop prevention cache
CACHE = defaultdict(lambda: deque(maxlen=2))

def clean(raw: str) -> str:
    """
    Clean raw text by removing leaked tags and formatting.
    
    Args:
        raw: Raw text from LLM
        
    Returns:
        Cleaned text
    """
    try:
        # Remove leaked tags like [CONTEXT], [TERMS], etc.
        txt = TAG_RE.sub("", html.unescape(raw)).strip()
        
        # Capitalize if needed
        if txt and txt[0].islower():
            txt = txt[0].upper() + txt[1:]
        
        return txt
    except Exception as e:
        logger.error(f"Error in clean function: {e}")
        return raw

def is_repeat(uid: str, answer: str) -> bool:
    """
    Check if this answer is a repeat for the user.
    
    Args:
        uid: User identifier
        answer: Current answer
        
    Returns:
        True if repeat detected, False otherwise
    """
    try:
        cache = CACHE[uid]
        if answer in cache:
            return True
        cache.append(answer)
        return False
    except Exception as e:
        logger.error(f"Error in is_repeat: {e}")
        return False

def polish(user_id: str, raw_answer: str, original_question: str) -> str:
    """
    Polish the answer with cleaning and loop prevention.
    
    Args:
        user_id: User identifier
        raw_answer: Raw answer from LLM
        original_question: Original user question
        
    Returns:
        Polished answer
    """
    try:
        # Clean the raw answer
        cleaned_answer = clean(raw_answer)
        
        # Check for repeats
        if is_repeat(user_id, cleaned_answer):
            return ("Looks like we covered that 🙂. "
                   "Try asking about strikes, expiry or risk.")
        
        return cleaned_answer
        
    except Exception as e:
        logger.error(f"Error in polish function: {e}")
        return raw_answer

def clear_user_cache(user_id: str):
    """Clear the cache for a specific user."""
    if user_id in CACHE:
        del CACHE[user_id]
        logger.info(f"Cleared cache for user {user_id}")

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    total_users = len(CACHE)
    total_entries = sum(len(cache) for cache in CACHE.values())
    
    return {
        "total_users": total_users,
        "total_entries": total_entries,
        "max_cache_size": 2
    }

