import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key in ("request_id", "job_id", "target_id", "agent_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)
