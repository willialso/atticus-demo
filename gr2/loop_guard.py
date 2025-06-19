# gr2/loop_guard.py
# Loop prevention system for Golden Retriever 2.0

import time
import hashlib
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class LoopGuard:
    """
    Prevents repetitive questions and provides graceful fallbacks.
    """
    
    def __init__(self, max_repetitions: int = 2, ttl_hours: int = 1):
        """
        Initialize loop guard.
        
        Args:
            max_repetitions: Maximum times a question can be asked
            ttl_hours: Time to live for question cache in hours
        """
        self.max_repetitions = max_repetitions
        self.ttl_seconds = ttl_hours * 3600
        self.question_cache: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        self.fallback_responses = [
            "Looks like we've covered that 🙂. Try asking about strikes, Greeks, or expiries!",
            "We just talked about that! How about learning about delta, gamma, or theta instead?",
            "Great question, but we've covered it already! Want to explore volatility or hedging?",
            "I've already explained that one! Let's dive into something new - maybe option strategies?",
            "We just went over that! How about we look at time decay or implied volatility?"
        ]
        self.fallback_index = 0
    
    def _hash_question(self, question: str, user_id: str) -> str:
        """
        Create a hash for the question + user combination.
        
        Args:
            question: User's question
            user_id: User identifier
            
        Returns:
            Hash string
        """
        # Normalize question for better matching
        normalized = question.lower().strip()
        normalized = ' '.join(normalized.split())  # Remove extra whitespace
        
        # Create hash
        content = f"{user_id}:{normalized}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _clean_old_entries(self, user_id: str):
        """
        Remove old entries from cache for a user.
        
        Args:
            user_id: User identifier
        """
        current_time = time.time()
        cutoff_time = current_time - self.ttl_seconds
        
        if user_id in self.question_cache:
            self.question_cache[user_id] = [
                (timestamp, question_hash) 
                for timestamp, question_hash in self.question_cache[user_id]
                if timestamp > cutoff_time
            ]
    
    def check_loop(self, question: str, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if question is a loop and return appropriate response.
        
        Args:
            question: User's question
            user_id: User identifier
            
        Returns:
            Tuple of (is_loop, fallback_response)
        """
        # Clean old entries
        self._clean_old_entries(user_id)
        
        # Hash the question
        question_hash = self._hash_question(question, user_id)
        current_time = time.time()
        
        # Check if question exists in cache
        if user_id in self.question_cache:
            question_count = sum(1 for _, qh in self.question_cache[user_id] if qh == question_hash)
            
            if question_count >= self.max_repetitions:
                # Get fallback response
                fallback = self._get_fallback_response()
                logger.info(f"Loop detected for user {user_id}: {question[:50]}...")
                return True, fallback
        
        # Add question to cache
        self.question_cache[user_id].append((current_time, question_hash))
        
        return False, None
    
    def _get_fallback_response(self) -> str:
        """
        Get a fallback response, cycling through options.
        
        Returns:
            Fallback response string
        """
        response = self.fallback_responses[self.fallback_index]
        self.fallback_index = (self.fallback_index + 1) % len(self.fallback_responses)
        return response
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dictionary with cache stats
        """
        total_entries = sum(len(entries) for entries in self.question_cache.values())
        unique_users = len(self.question_cache)
        
        return {
            "total_entries": total_entries,
            "unique_users": unique_users,
            "max_repetitions": self.max_repetitions,
            "ttl_hours": self.ttl_seconds // 3600
        }
    
    def clear_cache(self, user_id: Optional[str] = None):
        """
        Clear cache for specific user or all users.
        
        Args:
            user_id: User identifier, or None for all users
        """
        if user_id:
            if user_id in self.question_cache:
                del self.question_cache[user_id]
                logger.info(f"Cleared cache for user {user_id}")
        else:
            self.question_cache.clear()
            logger.info("Cleared all cache entries")

# Global instance
loop_guard = LoopGuard() 