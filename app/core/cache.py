from cachetools import TTLCache
from app.models.user_model import User
from datetime import datetime, timezone


# ── User cache ─────────────────────────────────────────────────────────────────
# Stores User objects keyed by user_id string.
# 5 minute TTL — short enough that admin suspensions take effect quickly,
# long enough to meaningfully reduce DB hits on every authenticated request.

_user_cache: TTLCache = TTLCache(maxsize=500, ttl=300)


class UserCacheService:

    @staticmethod
    def get(user_id: str) -> User | None:
        return _user_cache.get(user_id)

    @staticmethod
    def set(user_id: str, user: User) -> None:
        _user_cache[user_id] = user

    @staticmethod
    def invalidate(user_id: str) -> None:
        _user_cache.pop(user_id, None)


# ── Token block-list ────────────────────────────────────────────────────────────
# Stores invalidated access tokens until they naturally expire.
# Cannot use TTLCache here because each token has a different remaining lifetime.
# Uses a plain dict with expiry timestamps and lazy eviction on access.

_blockList: dict[str, float] = {}  # token → expiry unix timestamp


class TokenBlockListService:

    @staticmethod
    def add(token: str, ttl_seconds: int) -> None:
        """Blocklist a token for ttl_seconds from now."""
        _blockList[token] = datetime.now(
            timezone.utc).timestamp() + ttl_seconds

    @staticmethod
    def is_blocked(token: str) -> bool:
        """Returns True if token is block-listed and not yet expired."""
        expires_at = _blockList.get(token)
        if expires_at is None:
            return False
        if datetime.now(timezone.utc).timestamp() > expires_at:
            del _blockList[token]  # lazy eviction
            return False
        return True

    @staticmethod
    def cleanup() -> int:
        """Remove all expired entries. Called by APScheduler every 30 minutes."""
        now = datetime.now(timezone.utc).timestamp()
        expired = [k for k, exp in _blockList.items() if now > exp]
        for key in expired:
            del _blockList[key]
        return len(expired)
