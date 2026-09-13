"""Compatibility for GenerationSpanData in the pinned tracing integration.

Uses internal integration methods; recheck when upgrading OpenLLMetry.
"""

import json
from functools import wraps

from agents.tracing.span_data import GenerationSpanData
from opentelemetry.instrumentation.openai_agents import _hooks


def install_generation_compat():
    processor = _hooks.OpenTelemetryTracingProcessor
    original = processor._end_generation_span

    if getattr(original, "_cartwheel_generation_compat", False):
        return

    @wraps(original)
    def record_generation(self, span, data, trace_content):
        original(self, span, data, trace_content)

        if not isinstance(data, GenerationSpanData):
            return

        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = (data.usage or {}).get(field)
            if value is not None:
                span.set_attribute(f"gen_ai.usage.{field}", value)

        if trace_content:
            messages = []
            for message in data.output or []:
                role, parts = _hooks._convert_chat_message(dict(message))
                if role and parts:
                    messages.append({"role": role, "parts": parts})

            if messages:
                span.set_attribute(
                    "gen_ai.output.messages", json.dumps(messages)
                )

    record_generation._cartwheel_generation_compat = True
    processor._end_generation_span = record_generation
