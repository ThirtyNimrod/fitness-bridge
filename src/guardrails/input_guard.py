import base64
import binascii
import re

ALLOWED_KEYWORDS = [
    "workout", "training", "exercise", "sleep", "recovery", "fatigue",
    "readiness", "progress", "volume", "reps", "sets", "weight",
    "hrv", "heart rate", "muscle", "strength", "cardio", "nutrition",
    "session", "routine", "week", "month", "yesterday", "today",
    "strava", "fitbit", "hevy", "hello", "hi", "hey"
]

BLOCKED_PATTERNS = [
    "how to hack", "ignore previous", "jailbreak", "pretend you are", "ignore all instructions", "system prompt"
]


def _normalize_text(value: str) -> str:
    lowered = value.lower()
    # Collapse punctuation/spacing tricks used in obfuscated jailbreak strings.
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _maybe_decode_base64(value: str):
    compact = re.sub(r"\s+", "", value)
    if len(compact) < 12 or len(compact) % 4 != 0:
        return None
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
        return None
    try:
        decoded = base64.b64decode(compact, validate=True).decode("utf-8", errors="ignore")
    except (ValueError, binascii.Error):
        return None
    return decoded


class InputGuardrail:
    def check(self, query, llm=None):
        lower_query = query.lower()
        normalized_query = _normalize_text(query)
        
        for pattern in BLOCKED_PATTERNS:
            if pattern in lower_query or _normalize_text(pattern) in normalized_query:
                return False, "Blocked: policy violation"

        decoded = _maybe_decode_base64(query)
        if decoded:
            decoded_lower = decoded.lower()
            decoded_normalized = _normalize_text(decoded)
            for pattern in BLOCKED_PATTERNS:
                if pattern in decoded_lower or _normalize_text(pattern) in decoded_normalized:
                    return False, "Blocked: encoded policy violation"
                
        result = self.quick_filter(query)
        if result is not None:
            return result
            
        if llm is not None:
            return self.llm_classify(query, llm)
            
        return True, "Allowed"

    def quick_filter(self, query):
        lower = query.lower()
        for keyword in ALLOWED_KEYWORDS:
            if keyword in lower:
                return True, "Allowed by keyword"
                
        if len(query.split()) <= 4:
            return True, "Allowed (short query)"
            
        return None

    def llm_classify(self, query, llm):
        prompt = f"""
        You are a classifier for a personal fitness coaching app.
        The app only handles: workout analysis, recovery, sleep, training load, progress.

        Query: "{query}"

        Is this query related to fitness, health, training, or recovery?
        Reply with only: ALLOWED or BLOCKED
        """
        result = llm.invoke(prompt).content.strip().upper()
        if "ALLOWED" in result:
            return True, "Allowed by LLM classification"
        return False, "Not related to fitness"
