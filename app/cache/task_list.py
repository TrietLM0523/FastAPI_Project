import hashlib
import json
import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger("app")


class TaskListCache:
    def __init__(
        self,
        client: Any | None = None,
        *,
        enabled: bool = False,
        ttl_seconds: int = 60,
    ) -> None:
        self.client = client
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _normalized_query(query: Mapping[str, object]) -> str:
        normalized = {
            key: getattr(value, "value", value)
            for key, value in sorted(query.items())
            if value is not None
        }
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"))

    @classmethod
    def query_hash(cls, query: Mapping[str, object]) -> str:
        payload = cls._normalized_query(query).encode()
        return hashlib.sha256(payload).hexdigest()[:20]

    @staticmethod
    def version_key(project_id: int) -> str:
        return f"project:{project_id}:tasks:version"

    async def _version(self, project_id: int) -> int:
        if not self.enabled or self.client is None:
            return 0
        try:
            raw_version = await self.client.get(self.version_key(project_id))
            return int(raw_version or 0)
        except Exception:
            logger.warning("Redis version lookup failed; using database fallback")
            return 0

    async def key(self, project_id: int, query: Mapping[str, object]) -> str:
        version = await self._version(project_id)
        return f"project:{project_id}:tasks:v{version}:{self.query_hash(query)}"

    async def get(
        self, project_id: int, query: Mapping[str, object]
    ) -> dict[str, Any] | None:
        if not self.enabled or self.client is None:
            return None
        try:
            raw_value = await self.client.get(await self.key(project_id, query))
            if raw_value is None:
                return None
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")
            parsed = json.loads(raw_value)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            logger.warning("Redis read failed; using database fallback")
            return None

    async def set(
        self,
        project_id: int,
        query: Mapping[str, object],
        payload: Mapping[str, object],
    ) -> None:
        if not self.enabled or self.client is None:
            return
        try:
            await self.client.setex(
                await self.key(project_id, query),
                self.ttl_seconds,
                json.dumps(payload, separators=(",", ":")),
            )
        except Exception:
            logger.warning("Redis write failed; response was served from database")

    async def invalidate(self, project_id: int) -> None:
        if not self.enabled or self.client is None:
            return
        try:
            await self.client.incr(self.version_key(project_id))
        except Exception:
            logger.warning("Redis invalidation failed; database remains authoritative")
