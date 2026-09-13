import json
from types import SimpleNamespace

import pytest
from agents.tracing.span_data import GenerationSpanData, ResponseSpanData
from opentelemetry.instrumentation.openai_agents import _hooks

from observability.generation_compat import install_generation_compat


class RecordedSpan:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


@pytest.fixture
def handler(monkeypatch):
    processor = _hooks.OpenTelemetryTracingProcessor
    # Restore the original handler after each test.
    monkeypatch.setattr(
        processor, "_end_generation_span", processor._end_generation_span
    )
    install_generation_compat()
    return processor._end_generation_span


@pytest.mark.parametrize("capture_content", [True, False])
def test_claude_usage_and_messages(handler, capture_content):
    data = GenerationSpanData(
        input=[{"role": "user", "content": "Find my order"}],
        output=[{
            "role": "assistant",
            "content": "I will check.",
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "get_order",
                    "arguments": '{"order_id":4127}',
                },
            }],
        }],
        usage={
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        },
    )
    span = RecordedSpan()
    handler(None, span, data, capture_content)

    for field, count in data.usage.items():
        assert span.attributes[f"gen_ai.usage.{field}"] == count

    if capture_content:
        messages = json.loads(span.attributes["gen_ai.output.messages"])
        assert messages == [{
            "role": "assistant",
            "parts": [
                {"type": "text", "content": "I will check."},
                {
                    "type": "tool_call",
                    "id": "call-1",
                    "name": "get_order",
                    "arguments": {"order_id": 4127},
                },
            ],
        }]
        assert "gen_ai.input.messages" in span.attributes
    else:
        assert "gen_ai.input.messages" not in span.attributes
        assert "gen_ai.output.messages" not in span.attributes


def test_installation_is_not_repeated(handler):
    install_generation_compat()
    assert _hooks.OpenTelemetryTracingProcessor._end_generation_span is handler


def test_openai_response_recording_is_preserved(handler):
    response = SimpleNamespace(
        model="sample-openai-model",
        output=[SimpleNamespace(
            type="message",
            role="assistant",
            content=[SimpleNamespace(type="output_text", text="Hello")],
        )],
        usage=SimpleNamespace(
            input_tokens=12, output_tokens=3, total_tokens=15
        ),
    )
    span = RecordedSpan()
    handler(None, span, ResponseSpanData(response=response), True)

    assert span.attributes["gen_ai.response.model"] == "sample-openai-model"
    assert span.attributes["gen_ai.usage.input_tokens"] == 12
    assert span.attributes["gen_ai.usage.output_tokens"] == 3
    assert json.loads(span.attributes["gen_ai.output.messages"]) == [{
        "role": "assistant",
        "parts": [{"type": "text", "content": "Hello"}],
        "finish_reason": "",
    }]
