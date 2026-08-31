import bleach

MAX_TEXT_LENGTH = 8000  

def sanitize_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    if not text:
        return text
    cleaned = bleach.clean(text, tags=[], attributes={}, strip=True)
    return cleaned[:max_length]
