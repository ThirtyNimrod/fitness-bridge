import diskcache
from config import CACHE_DIR, CACHE_TTL_SECS

# Singleton cache
_cache = diskcache.Cache(CACHE_DIR)

def cached(ttl=CACHE_TTL_SECS, ignore=()):
    """
    Decorator that wraps any function with TTL-aware caching.
    Leverages diskcache's built-in memoize mechanism.
    """
    def decorator(func):
        return _cache.memoize(expire=ttl, ignore=ignore)(func)
    return decorator

def invalidate(key):
    """
    Deletes a specific key from the cache.
    Note: memoize keys are typically function names with their arguments.
    """
    if key in _cache:
        del _cache[key]

def get_cache():
    """
    Returns the underlying cache instance.
    """
    return _cache
