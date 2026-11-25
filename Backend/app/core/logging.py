import logging.config
import json
from datetime import datetime, timezone


class StructuredFormatter:
    def format(self, record):
        item = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("repository_id", "job_id", "stage", "progress", "files_discovered", "files_processed", "files_skipped", "worker_id", "elapsed_seconds", "imports"):
            if hasattr(record, key):
                item[key] = getattr(record, key)
        if record.exc_info:
            item["exception"] = self.formatException(record.exc_info)
        return json.dumps(item, ensure_ascii=False, default=str)

    def formatException(self, exc_info):
        import traceback
        return "".join(traceback.format_exception(*exc_info))


def configure_logging() -> None:
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"structured": {"()": StructuredFormatter}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "structured"}},
        "root": {"level": "INFO", "handlers": ["console"]},
    })
