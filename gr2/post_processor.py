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

