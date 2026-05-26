import logging
import sys


# ── Formatter ─────────────────────────────────────────────────────────────────

class ExtraFormatter(logging.Formatter):
    """
    Formats log records as:
      2026-05-17 10:23:45 | INFO     | app.services.pdf_loader | event_name | key=val key2=val2

    Any key=value pairs passed via extra={} are appended at the end.
    This makes logs both human-readable and grep/awk-friendly.
    """

    # Standard LogRecord attributes — we exclude these from the extras section
    _RESERVED = frozenset({
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "message", "module",
        "msecs", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)

        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in self._RESERVED
        }

        if extras:
            extra_str = " | " + "  ".join(f"{k}={v}" for k, v in extras.items())
            return base + extra_str

        return base


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure the root logger once at application startup.
    All module-level loggers inherit from the root automatically.

    Call this exactly once — inside the lifespan function in main.py.
    Calling it multiple times adds duplicate handlers and doubles every log line.
    """
    formatter = ExtraFormatter(
        fmt="{asctime} | {levelname:<8} | {name} | {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()

    # Guard: don't add handlers if setup_logging was already called
    if root.handlers:
        return

    root.setLevel(level)
    root.addHandler(handler)

    # Silence noisy third-party loggers that flood output with low-value lines
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("multipart.multipart").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.
    Always call with __name__ so the logger path mirrors the module path.

    Usage (at module level, outside any function):
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)

