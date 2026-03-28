from functools import lru_cache

from langchain_ollama import ChatOllama

from config import OLLAMA_MODEL, OLLAMA_BASE_URL


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.1):
    """Shared ChatOllama initializer to avoid repeated client construction."""
    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=float(temperature))
