"""
Billing module - Cost Calculator.

Computes the dynamic execution cost based on 5 components:
1. Base execution charge (per trigger)
2. Node action charges
3. LLM token cost (per provider and model)
4. Compute seconds (for code sandboxes)
5. Storage/Cache hit cost
"""
from __future__ import annotations

from decimal import Decimal

# Baseline hardware usage cost (e.g. AWS Lambda/Fargate execution equivalents per ms/MB)
_COMPUTE_COST_PER_GB_SECOND = Decimal("0.0000166667")  
_BASE_EXECUTION_CHARGE = Decimal("0.0001")
_STANDARD_NODE_CHARGE = Decimal("0.00001")


class LLMPricingRegistry:
    """Registry holding pricing per 1M tokens (Input / Output) for standard models."""
    
    # Prices in USD per 1M tokens as of early 2024
    _models: dict[str, tuple[Decimal, Decimal]] = {
        "gpt-4-turbo": (Decimal("10.00"), Decimal("30.00")),
        "gpt-4": (Decimal("30.00"), Decimal("60.00")),
        "gpt-3.5-turbo": (Decimal("0.50"), Decimal("1.50")),
        "claude-3-opus": (Decimal("15.00"), Decimal("75.00")),
        "claude-3-sonnet": (Decimal("3.00"), Decimal("15.00")),
        "claude-3-haiku": (Decimal("0.25"), Decimal("1.25")),
        "gemini-1.5-pro": (Decimal("3.50"), Decimal("10.50")),
        "gemini-1.5-flash": (Decimal("0.35"), Decimal("1.05")),
    }

    @classmethod
    def calculate_llm_cost(cls, model_name: str, input_tokens: int, output_tokens: int) -> Decimal:
        """
        Calculate the exact cost of a single LLM API call.
        Defaults to gpt-3.5-turbo equivalent pricing if model is unknown.
        """
        pricing = cls._models.get(model_name.lower())
        if not pricing:
            # Fallback conservative pricing to recover vague cost
            pricing = (Decimal("0.50"), Decimal("1.50"))

        input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * pricing[0]
        output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * pricing[1]
        
        return input_cost + output_cost


class CostCalculator:
    """Stateless cost calculator for execution segments."""

    @staticmethod
    def get_base_execution_cost() -> Decimal:
        """Fixed overhead charge per workflow execution."""
        return _BASE_EXECUTION_CHARGE

    @staticmethod
    def get_node_cost(node_type: str) -> Decimal:
        """Fixed cost for transiting a node (CPU cycles/state persistance)."""
        if node_type in ("llm", "search", "web_search"):
            return _STANDARD_NODE_CHARGE * 2
        return _STANDARD_NODE_CHARGE

    @staticmethod
    def calculate_compute_cost(duration_ms: int, memory_mb: int = 128) -> Decimal:
        """Compute sandbox usage cost based on duration and allocated memory."""
        seconds = Decimal(duration_ms) / Decimal(1000)
        gb = Decimal(memory_mb) / Decimal(1024)
        return seconds * gb * _COMPUTE_COST_PER_GB_SECOND
