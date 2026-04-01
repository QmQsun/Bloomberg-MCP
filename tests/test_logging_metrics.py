"""Tests for structured logging and tool call metrics."""

import pytest

from bloomberg_mcp.core.logging import ToolCallMetrics, log_tool_call


@pytest.fixture(autouse=True)
def reset_metrics():
    ToolCallMetrics.reset_instance()
    yield
    ToolCallMetrics.reset_instance()


class TestToolCallMetrics:
    def test_records_calls(self):
        m = ToolCallMetrics.get_instance()
        m.record("test_tool", duration_ms=100.0)
        m.record("test_tool", duration_ms=200.0, cache_hit=True)

        summary = m.summary
        assert "test_tool" in summary
        assert summary["test_tool"]["calls"] == 2
        assert summary["test_tool"]["cache_hits"] == 1
        assert summary["test_tool"]["avg_ms"] == 150.0
        assert summary["test_tool"]["max_ms"] == 200.0

    def test_records_errors(self):
        m = ToolCallMetrics.get_instance()
        m.record("fail_tool", duration_ms=50.0, error=True)
        m.record("fail_tool", duration_ms=60.0, error=False)

        summary = m.summary
        assert summary["fail_tool"]["errors"] == 1
        assert summary["fail_tool"]["error_rate"] == 50.0

    def test_multiple_tools_tracked_independently(self):
        m = ToolCallMetrics.get_instance()
        m.record("tool_a", duration_ms=100.0)
        m.record("tool_b", duration_ms=200.0)

        summary = m.summary
        assert "tool_a" in summary
        assert "tool_b" in summary
        assert summary["tool_a"]["calls"] == 1
        assert summary["tool_b"]["calls"] == 1


class TestLogToolCall:
    def test_context_manager_records_metrics(self):
        with log_tool_call("test_logged_tool") as ctx:
            ctx["result_size"] = 42

        m = ToolCallMetrics.get_instance()
        summary = m.summary
        assert "test_logged_tool" in summary
        assert summary["test_logged_tool"]["calls"] == 1
        assert summary["test_logged_tool"]["errors"] == 0

    def test_context_manager_records_error_on_exception(self):
        with pytest.raises(ValueError):
            with log_tool_call("test_error_tool"):
                raise ValueError("boom")

        m = ToolCallMetrics.get_instance()
        summary = m.summary
        assert summary["test_error_tool"]["errors"] == 1
