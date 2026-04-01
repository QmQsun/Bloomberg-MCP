"""Structured logging for Bloomberg MCP server.

Provides JSON-formatted structured logs with tool call metadata,
timing information, cache hit/miss tracking, and error context.
"""

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """JSON log formatter with Bloomberg-specific fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Append any extra fields passed via `extra={...}`
        for key in (
            "tool", "securities", "fields", "duration_ms",
            "cache_hit", "result_size", "error_count",
            "circuit_state", "throttle_remaining",
        ):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val

        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


def setup_logging(level: int = logging.INFO, structured: bool = True) -> None:
    """Configure root logger for Bloomberg MCP.

    Args:
        level: Logging level (default: INFO)
        structured: If True, use JSON formatter; otherwise standard.
    """
    root = logging.getLogger("bloomberg_mcp")
    if root.handlers:
        return  # Already configured

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if structured:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root.addHandler(handler)
    root.setLevel(level)


class ToolCallMetrics:
    """Singleton metrics collector for tool calls.

    Tracks per-tool call counts, durations, cache hits, and errors.
    Light-weight — no external dependencies.
    """

    _instance: Optional["ToolCallMetrics"] = None

    def __init__(self) -> None:
        self._metrics: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "ToolCallMetrics":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def record(
        self,
        tool: str,
        duration_ms: float,
        cache_hit: bool = False,
        error: bool = False,
    ) -> None:
        """Record a single tool call."""
        if tool not in self._metrics:
            self._metrics[tool] = {
                "calls": 0,
                "errors": 0,
                "cache_hits": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
            }
        m = self._metrics[tool]
        m["calls"] += 1
        m["total_ms"] += duration_ms
        if duration_ms > m["max_ms"]:
            m["max_ms"] = duration_ms
        if cache_hit:
            m["cache_hits"] += 1
        if error:
            m["errors"] += 1

    @property
    def summary(self) -> Dict[str, Any]:
        """Return per-tool summary metrics."""
        out: Dict[str, Any] = {}
        for tool, m in self._metrics.items():
            calls = m["calls"]
            out[tool] = {
                "calls": calls,
                "errors": m["errors"],
                "cache_hits": m["cache_hits"],
                "avg_ms": round(m["total_ms"] / calls, 1) if calls else 0,
                "max_ms": round(m["max_ms"], 1),
                "error_rate": round(m["errors"] / calls * 100, 1) if calls else 0,
                "cache_hit_rate": round(m["cache_hits"] / calls * 100, 1) if calls else 0,
            }
        return out


@contextmanager
def log_tool_call(tool_name: str, **extra_fields):
    """Context manager that logs tool call timing and metadata.

    Usage::

        with log_tool_call("bloomberg_get_reference_data",
                           securities=["AAPL US Equity"]) as ctx:
            result = do_work()
            ctx["cache_hit"] = False
            ctx["result_size"] = len(result)

    On exit it emits one structured log line and records metrics.
    """
    logger = logging.getLogger("bloomberg_mcp.handlers")
    ctx: Dict[str, Any] = {"cache_hit": False, "error": False, **extra_fields}
    start = time.perf_counter()

    try:
        yield ctx
    except Exception:
        ctx["error"] = True
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000

        log_extra = {
            "tool": tool_name,
            "duration_ms": round(duration_ms, 1),
            "cache_hit": ctx.get("cache_hit", False),
        }
        for k in ("securities", "fields", "result_size", "error_count"):
            if k in ctx:
                log_extra[k] = ctx[k]

        if ctx.get("error"):
            logger.error("tool_call_failed", extra=log_extra)
        else:
            logger.info("tool_call", extra=log_extra)

        ToolCallMetrics.get_instance().record(
            tool=tool_name,
            duration_ms=duration_ms,
            cache_hit=ctx.get("cache_hit", False),
            error=ctx.get("error", False),
        )
