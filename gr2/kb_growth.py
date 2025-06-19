# gr2/kb_growth.py
# Knowledge Base Growth System for Golden Retriever 2.0

import csv
import os
import logging
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class KBGrowthTracker:
    """Track missed questions and suggest new knowledge base content."""
    
    def __init__(self, logs_dir: str = "logs", misses_file: str = "misses.csv"):
        self.logs_dir = Path(logs_dir)
        self.misses_file = self.logs_dir / misses_file
        self._ensure_logs_dir()
        self._init_misses_file()
    
    def _ensure_logs_dir(self):
        """Ensure the logs directory exists."""
        self.logs_dir.mkdir(exist_ok=True)
    
    def _init_misses_file(self):
        """Initialize the misses CSV file with headers if it doesn't exist."""
        if not self.misses_file.exists():
            with open(self.misses_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'question',
                    'confidence',
                    'retrieved_docs_count',
                    'user_id',
                    'screen_context'
                ])
    
    def log_miss(self, question: str, confidence: float, retrieved_docs_count: int, 
                 user_id: str = None, screen_context: str = None):
        """
        Log a missed question for knowledge base improvement.
        
        Args:
            question: User question that wasn't answered well
            confidence: Confidence score of the response
            retrieved_docs_count: Number of documents retrieved
            user_id: User identifier
            screen_context: Screen context when question was asked
        """
        try:
            with open(self.misses_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    question,
                    confidence,
                    retrieved_docs_count,
                    user_id or "unknown",
                    screen_context or "none"
                ])
            logger.info(f"Logged missed question: {question[:50]}...")
        except Exception as e:
            logger.error(f"Error logging missed question: {e}")
    
    def get_misses_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get summary of missed questions for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Summary statistics
        """
        try:
            if not self.misses_file.exists():
                return {"total_misses": 0, "recent_misses": 0, "common_themes": []}
            
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            total_misses = 0
            recent_misses = 0
            questions = []
            
            with open(self.misses_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_misses += 1
                    try:
                        question_time = datetime.fromisoformat(row['timestamp'])
                        if question_time >= cutoff_date:
                            recent_misses += 1
                            questions.append(row['question'])
                    except:
                        pass
            
            # Simple theme analysis
            common_themes = self._analyze_themes(questions)
            
            return {
                "total_misses": total_misses,
                "recent_misses": recent_misses,
                "days_analyzed": days,
                "common_themes": common_themes
            }
            
        except Exception as e:
            logger.error(f"Error getting misses summary: {e}")
            return {"error": str(e)}
    
    def _analyze_themes(self, questions: List[str]) -> List[str]:
        """Analyze common themes in missed questions."""
        try:
            # Simple keyword analysis
            keywords = [
                "volatility", "implied", "iv", "skew", "term structure",
                "liquidity", "spread", "bid", "ask", "slippage",
                "margin", "collateral", "leverage", "position sizing",
                "portfolio", "correlation", "diversification", "hedging",
                "strategy", "spread", "straddle", "strangle", "butterfly",
                "calendar", "diagonal", "iron condor", "butterfly spread"
            ]
            
            theme_counts = {}
            for question in questions:
                question_lower = question.lower()
                for keyword in keywords:
                    if keyword in question_lower:
                        theme_counts[keyword] = theme_counts.get(keyword, 0) + 1
            
            # Return top themes
            sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
            return [theme for theme, count in sorted_themes[:5]]
            
        except Exception as e:
            logger.error(f"Error analyzing themes: {e}")
            return []
    
    def suggest_kb_improvements(self) -> List[Dict[str, str]]:
        """
        Suggest knowledge base improvements based on missed questions.
        
        Returns:
            List of suggested improvements
        """
        try:
            summary = self.get_misses_summary(days=30)
            suggestions = []
            
            if summary.get("recent_misses", 0) > 10:
                suggestions.append({
                    "type": "high_misses",
                    "title": "High Miss Rate",
                    "description": f"High number of missed questions ({summary['recent_misses']} in 30 days). Consider expanding knowledge base.",
                    "priority": "high"
                })
            
            for theme in summary.get("common_themes", []):
                suggestions.append({
                    "type": "missing_topic",
                    "title": f"Missing: {theme.title()}",
                    "description": f"Multiple questions about {theme} suggest this topic needs coverage.",
                    "priority": "medium"
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting improvements: {e}")
            return []

# Global instance
kb_tracker = KBGrowthTracker() 