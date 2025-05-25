# backend/sentiment_analyzer.py
import requests
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
from textblob import TextBlob
import feedparser
from urllib.parse import quote

from backend import config
from backend.utils import setup_logger

logger = setup_logger(__name__)

@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    timestamp: datetime
    source: str
    sentiment_score: float
    relevance_score: float
    impact_score: float

@dataclass
class SentimentSignal:
    overall_sentiment: float  # -1 to 1
    news_volume: int
    fear_greed_index: Optional[float]
    social_sentiment: float
    confidence: float
    key_events: List[str]
    timestamp: datetime

class SentimentAnalyzer:
    """Analyzes market sentiment from news, social media, and fear/greed data."""
    
    def __init__(self):
        self.news_sources = {
            "coindesk": "https://feeds.coindesk.com/",
            "cointelegraph": "https://cointelegraph.com/rss",
            "bitcoin_com": "https://news.bitcoin.com/feed/",
            "decrypt": "https://decrypt.co/feed"
        }
        
        self.bitcoin_keywords = [
            'bitcoin', 'btc', 'cryptocurrency', 'crypto', 'blockchain',
            'digital currency', 'satoshi', 'mining', 'hash rate',
            'lightning network', 'taproot', 'segwit'
        ]
        
        self.positive_keywords = [
            'adoption', 'bullish', 'rally', 'surge', 'breakthrough',
            'milestone', 'partnership', 'institutional', 'mainstream',
            'upgrade', 'improvement', 'breakthrough', 'record', 'high'
        ]
        
        self.negative_keywords = [
            'crash', 'dump', 'bearish', 'decline', 'correction',
            'regulation', 'ban', 'hack', 'security', 'vulnerability',
            'fraud', 'ponzi', 'bubble', 'crash', 'panic'
        ]
        
        self.news_cache = []
        self.sentiment_history = []
        
    def fetch_news_feeds(self) -> List[NewsItem]:
        """Fetch news from RSS feeds."""
        news_items = []
        
        for source_name, feed_url in self.news_sources.items():
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # Latest 10 articles per source
                    # Parse publish date
                    pub_date = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    
                    # Skip old news (older than 24 hours)
                    if datetime.now() - pub_date > timedelta(hours=24):
                        continue
                    
                    title = entry.get('title', '')
                    summary = entry.get('summary', entry.get('description', ''))
                    url = entry.get('link', '')
                    
                    # Calculate relevance to Bitcoin
                    relevance = self._calculate_relevance(title, summary)
                    
                    if relevance > 0.3:  # Only keep relevant news
                        # Calculate sentiment
                        sentiment = self._analyze_text_sentiment(title + " " + summary)
                        
                        # Calculate impact score
                        impact = self._calculate_impact_score(title, summary, source_name)
                        
                        news_item = NewsItem(
                            title=title,
                            summary=summary,
                            url=url,
                            timestamp=pub_date,
                            source=source_name,
                            sentiment_score=sentiment,
                            relevance_score=relevance,
                            impact_score=impact
                        )
                        
                        news_items.append(news_item)
                        
            except Exception as e:
                logger.warning(f"Failed to fetch news from {source_name}: {e}")
                
        return news_items
    
    def _calculate_relevance(self, title: str, summary: str) -> float:
        """Calculate how relevant the news is to Bitcoin."""
        text = (title + " " + summary).lower()
        
        keyword_score = 0
        for keyword in self.bitcoin_keywords:
            if keyword.lower() in text:
                keyword_score += 1
                
        # Weight title keywords more heavily
        title_score = 0
        for keyword in self.bitcoin_keywords:
            if keyword.lower() in title.lower():
                title_score += 2
                
        total_score = keyword_score + title_score
        max_possible = len(self.bitcoin_keywords) * 3  # All keywords in title
        
        return min(total_score / max_possible, 1.0)
    
    def _analyze_text_sentiment(self, text: str) -> float:
        """Analyze sentiment of text using TextBlob and keyword analysis."""
        # TextBlob sentiment
        blob = TextBlob(text)
        textblob_sentiment = blob.sentiment.polarity
        
        # Keyword-based sentiment
        text_lower = text.lower()
        positive_count = sum(1 for word in self.positive_keywords if word in text_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in text_lower)
        
        if positive_count + negative_count > 0:
            keyword_sentiment = (positive_count - negative_count) / (positive_count + negative_count)
        else:
            keyword_sentiment = 0
        
        # Combine sentiments (weighted average)
        combined_sentiment = 0.6 * textblob_sentiment + 0.4 * keyword_sentiment
        
        return np.clip(combined_sentiment, -1, 1)
    
    def _calculate_impact_score(self, title: str, summary: str, source: str) -> float:
        """Calculate potential market impact of news."""
        impact_score = 0.5  # Base score
        
        # Source credibility
        source_weights = {
            "coindesk": 1.2,
            "cointelegraph": 1.0,
            "bitcoin_com": 0.9,
            "decrypt": 0.8
        }
        impact_score *= source_weights.get(source, 0.7)
        
        # High-impact keywords
        high_impact_keywords = [
            'sec', 'regulation', 'etf', 'institutional', 'tesla', 'microstrategy',
            'federal reserve', 'fed', 'inflation', 'monetary policy', 'treasury',
            'sanctions', 'adoption', 'legal tender', 'ban', 'government'
        ]
        
        text = (title + " " + summary).lower()
        for keyword in high_impact_keywords:
            if keyword in text:
                impact_score += 0.2
                
        # Title prominence
        if any(keyword in title.lower() for keyword in self.bitcoin_keywords):
            impact_score += 0.3
            
        return min(impact_score, 2.0)
    
    def fetch_fear_greed_index(self) -> Optional[float]:
        """Fetch Fear & Greed Index from API."""
        try:
            # Alternative.me Fear & Greed Index API
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    value = int(data['data'][0]['value'])
                    # Convert to -1 to 1 scale (0-24: extreme fear, 25-49: fear, 50-74: greed, 75-100: extreme greed)
                    normalized_value = (value - 50) / 50  # Centers around 0
                    return np.clip(normalized_value, -1, 1)
                    
        except Exception as e:
            logger.warning(f"Failed to fetch Fear & Greed Index: {e}")
            
        return None
    
    def analyze_social_sentiment(self) -> float:
        """Analyze social media sentiment (simplified implementation)."""
        # This is a placeholder for social media sentiment analysis
        # In production, you would integrate with Twitter API, Reddit API, etc.
        
        # For demo, return a random walk around neutral with some persistence
        if hasattr(self, '_last_social_sentiment'):
            # Persistent random walk
            change = np.random.normal(0, 0.1)
            new_sentiment = self._last_social_sentiment + change
            self._last_social_sentiment = np.clip(new_sentiment, -1, 1)
        else:
            self._last_social_sentiment = 0.0
            
        return self._last_social_sentiment
    
    def generate_sentiment_signal(self) -> SentimentSignal:
        """Generate comprehensive sentiment signal."""
        # Fetch recent news
        news_items = self.fetch_news_feeds()
        
        # Calculate overall news sentiment
        if news_items:
            # Weight by relevance and impact
            weighted_sentiments = []
            for item in news_items:
                weight = item.relevance_score * item.impact_score
                weighted_sentiments.extend([item.sentiment_score] * int(weight * 10))
            
            news_sentiment = np.mean(weighted_sentiments) if weighted_sentiments else 0
        else:
            news_sentiment = 0
        
        # Get Fear & Greed Index
        fear_greed = self.fetch_fear_greed_index()
        
        # Get social sentiment
        social_sentiment = self.analyze_social_sentiment()
        
        # Combine all signals
        signals = [news_sentiment]
        weights = [0.4]  # News weight
        
        if fear_greed is not None:
            signals.append(fear_greed)
            weights.append(0.4)  # Fear/Greed weight
            
        signals.append(social_sentiment)
        weights.append(0.2)  # Social weight
        
        # Normalize weights
        weights = np.array(weights)
        weights = weights / weights.sum()
        
        overall_sentiment = np.average(signals, weights=weights)
        
        # Calculate confidence based on signal agreement
        signal_std = np.std(signals) if len(signals) > 1 else 0
        confidence = max(0, 1 - signal_std)  # Lower std = higher confidence
        
        # Extract key events from news
        key_events = []
        for item in sorted(news_items, key=lambda x: x.impact_score, reverse=True)[:3]:
            if item.impact_score > 1.0:
                key_events.append(item.title[:100])  # Truncate long titles
        
        # Store in history
        signal = SentimentSignal(
            overall_sentiment=overall_sentiment,
            news_volume=len(news_items),
            fear_greed_index=fear_greed,
            social_sentiment=social_sentiment,
            confidence=confidence,
            key_events=key_events,
            timestamp=datetime.now()
        )
        
        self.sentiment_history.append(signal)
        if len(self.sentiment_history) > 1000:  # Limit memory
            self.sentiment_history = self.sentiment_history[-1000:]
            
        return signal
    
    def get_sentiment_trend(self, hours: int = 24) -> Dict[str, float]:
        """Get sentiment trend over specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_signals = [s for s in self.sentiment_history if s.timestamp >= cutoff_time]
        
        if len(recent_signals) < 2:
            return {"trend": 0, "momentum": 0, "volatility": 0}
        
        sentiments = [s.overall_sentiment for s in recent_signals]
        
        # Calculate trend (linear regression slope)
        x = np.arange(len(sentiments))
        trend = np.polyfit(x, sentiments, 1)[0] if len(sentiments) > 1 else 0
        
        # Calculate momentum (recent vs older sentiment)
        if len(sentiments) >= 4:
            recent_avg = np.mean(sentiments[-len(sentiments)//2:])
            older_avg = np.mean(sentiments[:len(sentiments)//2])
            momentum = recent_avg - older_avg
        else:
            momentum = 0
            
        # Calculate volatility
        volatility = np.std(sentiments) if len(sentiments) > 1 else 0
        
        return {
            "trend": trend,
            "momentum": momentum, 
            "volatility": volatility,
            "current_sentiment": sentiments[-1] if sentiments else 0,
            "samples": len(recent_signals)
        }
    
    def get_market_regime_from_sentiment(self) -> str:
        """Determine market regime based on sentiment analysis."""
        if len(self.sentiment_history) < 10:
            return "neutral"
            
        recent_sentiment = np.mean([s.overall_sentiment for s in self.sentiment_history[-10:]])
        sentiment_volatility = np.std([s.overall_sentiment for s in self.sentiment_history[-20:]])
        
        if recent_sentiment > 0.3 and sentiment_volatility < 0.2:
            return "bullish_stable"
        elif recent_sentiment > 0.1:
            return "bullish_volatile"
        elif recent_sentiment < -0.3 and sentiment_volatility < 0.2:
            return "bearish_stable"
        elif recent_sentiment < -0.1:
            return "bearish_volatile"
        else:
            return "neutral"
