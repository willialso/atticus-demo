# gr2/loop_guard.py
# Simple loop prevention for Golden Retriever 2.0

import time
import logging
from typing import Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

class LoopGuard:
    """Simple loop prevention mechanism to avoid repetitive responses."""
    
    def __init__(self, max_repetitions: int = 3, time_window: int = 300):
        self.max_repetitions = max_repetitions
        self.time_window = time_window  # 5 minutes
        self.user_history: Dict[str, list] = defaultdict(list)
    
    def check_loop(self, user_id: str, question: str) -> bool:
        """
        Check if user is in a loop with similar questions.
        
        Args:
            user_id: User identifier
            question: Current question
            
        Returns:
            True if loop detected, False otherwise
        """
        try:
            current_time = time.time()
            user_questions = self.user_history[user_id]
            
            # Clean old entries
            user_questions = [q for q in user_questions if current_time - q['timestamp'] < self.time_window]
            self.user_history[user_id] = user_questions
            
            # Check for similar questions
            question_lower = question.lower().strip()
            similar_count = 0
            
            for q in user_questions:
                if self._is_similar(question_lower, q['question']):
                    similar_count += 1
            
            # Add current question
            self.user_history[user_id].append({
                'question': question_lower,
                'timestamp': current_time
            })
            
            # Check if too many similar questions
            if similar_count >= self.max_repetitions:
                logger.info(f"Loop detected for user {user_id}: {similar_count} similar questions")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in loop guard: {e}")
            return False
    
    def _is_similar(self, question1: str, question2: str) -> bool:
        """
        Check if two questions are similar.
        
        Args:
            question1: First question
            question2: Second question
            
        Returns:
            True if similar, False otherwise
        """
        try:
            # Simple similarity check based on key terms
            key_terms = ['delta', 'gamma', 'theta', 'vega', 'strike', 'premium', 'call', 'put', 'option']
            
            # Extract key terms from both questions
            terms1 = [term for term in key_terms if term in question1]
            terms2 = [term for term in key_terms if term in question2]
            
            # If both questions contain the same key terms, consider them similar
            if terms1 and terms2 and set(terms1) == set(terms2):
                return True
            
            # Also check for exact matches (case-insensitive)
            if question1 == question2:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in similarity check: {e}")
            return False
    
    def clear_user_history(self, user_id: str):
        """Clear history for a specific user."""
        if user_id in self.user_history:
            del self.user_history[user_id]
            logger.info(f"Cleared history for user {user_id}")
    
    def get_stats(self) -> Dict:
        """Get loop guard statistics."""
        total_users = len(self.user_history)
        total_questions = sum(len(questions) for questions in self.user_history.values())
        
        return {
            "total_users": total_users,
            "total_questions": total_questions,
            "max_repetitions": self.max_repetitions,
            "time_window": self.time_window
        }

# Global instance
loop_guard = LoopGuard() 