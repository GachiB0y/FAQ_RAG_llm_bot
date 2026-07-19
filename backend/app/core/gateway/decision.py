from dataclasses import dataclass


@dataclass
class GatewayDecision:
    allowed: bool
    reason: str | None  # "rate_limited" | "injection" | None
    trace_id: str
    remaining: int | None = None
    limit: int | None = None
    reset_seconds: int | None = None
