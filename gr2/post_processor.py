# gr2/post_processor.py
# Post-processor for Golden Retriever 2.0 responses

import re, html, time
from collections import defaultdict

# -------- style rules -------------------------------------------------
GREETING = "Hi! "
BULLET   = "• "
TAG_RE   = re.compile(r"\[[A-Z][^]]+?\]")          # strips [Terms:], [Context:], etc.

# -------- loop guard --------------------------------------------------
SESSIONS       = defaultdict(lambda: {"q": None, "n": 0, "ts": time.time()})
MAX_REPEATS    = 2
SESSION_WINDOW = 3600            # seconds
FALLBACK_LOOP  = ("Looks like we just covered that 🙂. "
                  "Ask about strikes, Greeks, or expiries!")

def _too_repetitive(uid: str, q: str) -> bool:
    s = SESSIONS[uid]
    now = time.time()
    if now - s["ts"] > SESSION_WINDOW:
        s.update({"q": None, "n": 0})
    s["ts"] = now
    if s["q"] and s["q"].strip().lower() == q.strip().lower():
        s["n"] += 1
    else:
        s.update({"q": q, "n": 1})
    return s["n"] > MAX_REPEATS

def polish(uid: str, raw_resp: str, user_q: str) -> str:
    if _too_repetitive(uid, user_q):
        return FALLBACK_LOOP
    txt = TAG_RE.sub("", html.unescape(raw_resp)).strip()
    if not txt.lower().startswith(("hi", "hello", "hey")):
        txt = GREETING + txt[0].lower() + txt[1:]
    # bullet-ise long lines
    if "\n" not in txt and len(txt.split()) > 18:
        txt = BULLET + txt
    return txt

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