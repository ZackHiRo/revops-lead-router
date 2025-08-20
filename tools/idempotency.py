import time
import redis
import os
from loguru import logger

class Idem:
    """Redis-based idempotency checker to prevent duplicate lead processing."""
    
    def __init__(self):
        """Initialize Redis connection."""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.r = redis.from_url(redis_url)
            # Test connection
            self.r.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            # Fallback to in-memory storage (not recommended for production)
            self.r = None
            self._memory_keys = set()
    
    def check_and_set(self, key: str, ttl: int = 3600) -> bool:
        """
        Check if key exists and set it if it doesn't.
        
        Args:
            key: Unique identifier for the lead
            ttl: Time to live in seconds (default: 1 hour)
            
        Returns:
            True if key was set (new lead), False if already exists
        """
        if not key:
            logger.warning("Empty key provided to idempotency check")
            return False
        
        try:
            if self.r:
                # Use Redis
                result = self.r.set(
                    name=f"idem:{key}", 
                    value=int(time.time()), 
                    ex=ttl, 
                    nx=True
                )
                return result is True
            else:
                # Fallback to in-memory
                if key in self._memory_keys:
                    return False
                self._memory_keys.add(key)
                return True
                
        except Exception as e:
            logger.error(f"Idempotency check failed: {e}")
            # Fail open - allow processing to continue
            return True
    
    def get_processing_time(self, key: str) -> int:
        """Get when the lead was processed (for debugging)."""
        try:
            if self.r:
                timestamp = self.r.get(f"idem:{key}")
                return int(timestamp) if timestamp else 0
            else:
                return 0
        except Exception as e:
            logger.error(f"Failed to get processing time: {e}")
            return 0
    
    def clear_key(self, key: str) -> bool:
        """Manually clear a key (for testing/debugging)."""
        try:
            if self.r:
                return bool(self.r.delete(f"idem:{key}"))
            else:
                self._memory_keys.discard(key)
                return True
        except Exception as e:
            logger.error(f"Failed to clear key: {e}")
            return False
