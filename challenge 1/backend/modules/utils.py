import re

def chunk_text(text, chunk_size_chars=700, overlap_chars=150):
    chunks = []
    start = 0
    text_len = len(text)
    if text_len == 0: return []
    while start < text_len:
        end = min(start + chunk_size_chars, text_len)
        chunks.append(text[start:end])
        if end == text_len: break
        next_start = start + chunk_size_chars - overlap_chars
        if next_start <= start: next_start = start + 1 
        start = next_start
        if start >= text_len: break
    return [chunk for chunk in chunks if chunk.strip()]

def preprocess_text(text):
    text = str(text).lower() 
    text = re.sub(r'\s+', ' ', text).strip()
    return text