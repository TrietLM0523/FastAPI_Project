import json
import logging
from datetime import UTC, datetime

_HANDLER_MARKER = "_fastapi_practice_json_handler"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str | None = None) -> logging.Logger:
    configured_level = (level or "INFO").upper()

    for logger_name in ("app", "app.access"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(configured_level)
        logger.propagate = False

        if not any(
            getattr(handler, _HANDLER_MARKER, False) for handler in logger.handlers
        ):
            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
            setattr(handler, _HANDLER_MARKER, True)
            logger.addHandler(handler)

    return logging.getLogger("app")
