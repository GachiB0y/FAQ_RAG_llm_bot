from dataclasses import dataclass


@dataclass
class GatewayDecision:
    allowed: bool
    reason: str | None  # "rate_limited" | "injection" | None
    trace_id: str
