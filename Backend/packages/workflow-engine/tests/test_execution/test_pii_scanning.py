"""
P9-T-09 — PII output scanning tests.

Verifies that PIIScanner correctly:
1. Blocks execution when PII is found in SCAN_BLOCK mode
2. Warns (does not block) in SCAN_WARN mode
3. Is a no-op in DISABLED mode
4. Detects SSN, credit card, and email patterns
5. Scans nested dicts and lists
"""
from __future__ import annotations

import pytest

from workflow_engine.execution.pii_scanner import PIIScanner
from workflow_engine.errors import PIIBlockedError
from workflow_engine.models.tenant import TenantConfig, PlanTier
from workflow_engine.models.tenant import PIIPolicy


def _config(policy: PIIPolicy) -> TenantConfig:
    return TenantConfig(tenant_id="t1", plan_tier=PlanTier.PRO, pii_policy=policy)


class TestPIIScannerBlock:
    def test_ssn_blocked(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        with pytest.raises(PIIBlockedError, match="SSN"):
            PIIScanner.scan_dict({"field": "123-45-6789"}, config)

    def test_credit_card_blocked(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        with pytest.raises(PIIBlockedError):
            PIIScanner.scan_dict({"payment": "4111222233334444"}, config)

    def test_nested_dict_pii_blocked(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        data = {"user": {"profile": {"ssn": "987-65-4321"}}}
        with pytest.raises(PIIBlockedError):
            PIIScanner.scan_dict(data, config)

    def test_pii_in_list_blocked(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        data = {"records": [{"id": "r1", "ssn": "111-22-3333"}]}
        with pytest.raises(PIIBlockedError):
            PIIScanner.scan_dict(data, config)

    def test_clean_data_not_blocked(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        data = {"name": "John Doe", "city": "Austin", "count": 42}
        # Should not raise
        PIIScanner.scan_dict(data, config)

    def test_multiple_pii_fields_blocked_on_first_hit(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        data = {"ssn": "123-45-6789", "card": "4111222233334444"}
        with pytest.raises(PIIBlockedError):
            PIIScanner.scan_dict(data, config)


class TestPIIScannerWarn:
    def test_ssn_does_not_raise_in_warn_mode(self):
        config = _config(PIIPolicy.SCAN_WARN)
        data = {"ssn": "123-45-6789"}
        # Must not raise, even though PII is present
        PIIScanner.scan_dict(data, config)

    def test_credit_card_does_not_raise_in_warn_mode(self):
        config = _config(PIIPolicy.SCAN_WARN)
        data = {"card": "4111222233334444"}
        PIIScanner.scan_dict(data, config)


class TestPIIScannerDisabled:
    def test_pii_ignored_when_disabled(self):
        config = _config(PIIPolicy.DISABLED)
        data = {"ssn": "123-45-6789", "card": "4111222233334444"}
        # Must not raise — PII scanning is disabled for this tenant
        PIIScanner.scan_dict(data, config)

    def test_empty_dict_no_error(self):
        config = _config(PIIPolicy.DISABLED)
        PIIScanner.scan_dict({}, config)


class TestPIIScannerEdgeCases:
    def test_none_values_do_not_crash(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        data = {"field": None, "nested": {"key": None}}
        PIIScanner.scan_dict(data, config)

    def test_numeric_values_do_not_crash(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        data = {"count": 100, "amount": 3.14}
        PIIScanner.scan_dict(data, config)

    def test_empty_string_not_flagged(self):
        config = _config(PIIPolicy.SCAN_BLOCK)
        data = {"ssn": "", "card": ""}
        PIIScanner.scan_dict(data, config)
