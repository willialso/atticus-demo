# gr2/post_processor.py
# Post-processor for Golden Retriever 2.0 responses

import re
import html
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def clean_response(raw_text: str) -> str:
    """
    Clean and format Golden Retriever 2.0 responses for user-friendly output.
    
    Args:
        raw_text: Raw response from GR2
        
    Returns:
        Cleaned, user-friendly response
    """
    if not raw_text:
        return "Hi! I'm not sure about that. Could you try asking about options basics, Greeks, or trading strategies?"
    
    # Step 1: Strip system tags and metadata
    cleaned = raw_text
    
    # Remove [Terms: ...] tags
    cleaned = re.sub(r'\[Terms:[^\]]*\]', '', cleaned)
    
    # Remove [Context: ...] tags  
    cleaned = re.sub(r'\[Context:[^\]]*\]', '', cleaned)
    
    # Remove confidence scores and other metadata
    cleaned = re.sub(r'\[Confidence:[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\[Sources:[^\]]*\]', '', cleaned)
    
    # Step 2: Clean up HTML entities
    cleaned = html.unescape(cleaned)
    
    # Step 3: Remove extra whitespace and normalize
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    # Step 4: Add friendly greeting if not present
    if not cleaned.lower().startswith(('hi', 'hello', 'hey')):
        cleaned = f"Hi! {cleaned}"
    
    # Step 5: Ensure proper sentence structure
    if not cleaned.endswith(('.', '!', '?')):
        cleaned += '.'
    
    # Step 6: Keep it concise (max 2-3 sentences)
    sentences = re.split(r'[.!?]+', cleaned)
    if len(sentences) > 3:
        cleaned = '. '.join(sentences[:3]) + '.'
    
    return cleaned

def extract_jargon_terms(text: str) -> list:
    """
    Extract potential jargon terms from text for analogy requests.
    
    Args:
        text: Input text
        
    Returns:
        List of jargon terms found
    """
    jargon_patterns = [
        r'\bdelta\b', r'\bgamma\b', r'\btheta\b', r'\bvega\b',
        r'\bITM\b', r'\bOTM\b', r'\bATM\b', r'\bpremium\b',
        r'\bstrike\b', r'\bexpiry\b', r'\bvolatility\b',
        r'\bimplied volatility\b', r'\bintrinsic value\b',
        r'\btime value\b', r'\bhedging\b', r'\bassignment\b'
    ]
    
    found_terms = []
    for pattern in jargon_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            term = re.search(pattern, text, re.IGNORECASE).group()
            found_terms.append(term.lower())
    
    return list(set(found_terms))

def add_analogy_prompt(question: str, jargon_terms: list) -> str:
    """
    Enhance question with analogy request for jargon terms.
    
    Args:
        question: Original question
        jargon_terms: List of jargon terms found
        
    Returns:
        Enhanced question with analogy request
    """
    if not jargon_terms:
        return question
    
    analogy_request = f" Please explain any technical terms with simple analogies."
    return question + analogy_request

def format_bullet_points(text: str) -> str:
    """
    Convert long responses to bullet points for better readability.
    
    Args:
        text: Input text
        
    Returns:
        Formatted text with bullet points
    """
    # If text is long, convert to bullets
    if len(text) > 200:
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) > 2:
            bullet_text = "Hi! Here's what you need to know:\n"
            for sentence in sentences[:4]:  # Max 4 bullets
                if sentence:
                    bullet_text += f"• {sentence.strip()}.\n"
            return bullet_text.strip()
    
    return text 