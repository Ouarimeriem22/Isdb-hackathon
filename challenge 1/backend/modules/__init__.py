import re

def chunk_text(text, chunk_size_chars=700, overlap_chars=150):
    """
    Simple text chunker based on character count with overlap.
    More sophisticated methods might split by sentences or paragraphs.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size_chars - overlap_chars
        if start >= len(text):
            break
    return [chunk for chunk in chunks if chunk.strip()]

def preprocess_text(text):
    # Simple preprocessing: lowercase and remove extra whitespace
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text