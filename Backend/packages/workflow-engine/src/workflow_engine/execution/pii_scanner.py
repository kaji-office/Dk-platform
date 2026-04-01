"""PII detection scanner enforcing tenant policies.

D-4 GAP fixes applied:
- GAP-D4-2: Patterns use re.search() not anchored ^...$  (catches embedded PII)
- GAP-D4-3: Email and phone number patterns added to _RULES
- GAP-D4-1: SCAN_MASK branch returns masked value (not fall-through)
"""
from __future__ import annotations

import re
from typing import Any

from workflow_engine.errors import PIIBlockedError
from workflow_engine.models.tenant import PIIPolicy, TenantConfig

MASK_TOKEN = "[MASKED]"

# GAP-D4-2: Use re.search() patterns (no ^ / $ anchors) to catch embedded PII.
# GAP-D4-3: Email and phone number patterns added.
_RULES: dict[str, re.Pattern] = {
    "SSN": re.compile(r"\d{3}-\d{2}-\d{4}"),
    "CREDIT_CARD": re.compile(
        r"(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
        r"|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}"
        r"|(?:2131|1800|35\d{3})\d{11})"
    ),
    # GAP-D4-3: Email pattern
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    # GAP-D4-3: Phone number pattern (US + international formats)
    "PHONE": re.compile(
        r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})"
    ),
}


class PIIScanner:
    """Scans payload dictionaries recursively for tenant-blocked PII patterns."""

    @classmethod
    def check_value(cls, value: str, config: TenantConfig) -> str:
        """
        Check a single string value for PII and apply the tenant policy.

        Returns:
            The (potentially masked) value.

        Raises:
            PIIBlockedError: if policy is SCAN_BLOCK and PII is found.
        """
        if config.pii_policy == PIIPolicy.SCAN_WARN:
            return value  # Log-only, no mutation

        str_val = str(value)
        for name, regex in _RULES.items():
            if regex.search(str_val):
                if config.pii_policy == PIIPolicy.SCAN_BLOCK:
                    raise PIIBlockedError(f"PII {name} detected and blocked by policy")
                # GAP-D4-1: SCAN_MASK must redact and return masked value
                if config.pii_policy == PIIPolicy.SCAN_MASK:
                    str_val = regex.sub(MASK_TOKEN, str_val)

        return str_val

    @classmethod
    def scan_dict(cls, data: dict[str, Any], config: TenantConfig) -> dict[str, Any]:
        """
        Recursively traverse dictionaries and apply PII policy.

        Returns:
            A new dict with PII replaced by [MASKED] (SCAN_MASK) or
            the original dict unchanged (SCAN_WARN).

        Raises:
            PIIBlockedError: if SCAN_BLOCK and PII is found.
        """
        if config.pii_policy == PIIPolicy.SCAN_WARN:
            return data

        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = cls.scan_dict(value, config)
            elif isinstance(value, list) or isinstance(value, tuple):
                new_list = []
                for item in value:
                    if isinstance(item, dict):
                        new_list.append(cls.scan_dict(item, config))
                    elif isinstance(item, str):
                        new_list.append(cls.check_value(item, config))
                    else:
                        new_list.append(item)
                result[key] = type(value)(new_list)
            elif isinstance(value, str):
                result[key] = cls.check_value(value, config)
            else:
                result[key] = value
        return result
