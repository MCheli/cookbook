"""Rough per-token prices (USD per million tokens) for the usage estimate in Settings.

Only an estimate shown next to the user's own usage; the Anthropic console is the real bill.
"""

from __future__ import annotations

_PER_MILLION = {
    "opus": (5.0, 25.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    family = next((f for f in _PER_MILLION if f in model), "sonnet")
    inp, out = _PER_MILLION[family]
    return (input_tokens * inp + output_tokens * out) / 1_000_000
