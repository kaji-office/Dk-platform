"""
Privacy Handler - Orchestrates PIIDetector and PIIMasker with policy logic.
"""
from workflow_engine.models import PIIPolicy
from workflow_engine.errors import PIIBlockedError
from workflow_engine.privacy.detector import PIIDetector
from workflow_engine.privacy.masker import PIIMasker


class PrivacyHandler:
    """Interprets tenant policies to conditionally block or mask PII payload."""
    
    def __init__(self) -> None:
        self._detector = PIIDetector()
        self._masker = PIIMasker()

    def process_payload(self, text: str, policy: PIIPolicy) -> str:
        """
        Scan and act upon string payload depending on tenant PII configurations.
        
        Args:
            text: Application payload (e.g., prompt to LLM).
            policy: The configured Tenant PIIPolicy.
            
        Returns:
            The potentially modified/safe text, or raises exception if blocked.
        """
        if policy == PIIPolicy.SCAN_WARN:
            # We just let it pass through. A real application might log a warning
            # "PII present in payload", but we don't block.
            return text
            
        # Detect entities
        results = self._detector.analyze(text)
        
        if not results:
            return text
            
        if policy == PIIPolicy.SCAN_BLOCK:
            # Found entities, and tenant prefers hard blocks over LLM ingestion
            entities = set(r.entity_type for r in results)
            raise PIIBlockedError(
                f"PII detected and policy is SCAN_BLOCK. Entities: {entities}"
            )
            
        if policy == PIIPolicy.SCAN_MASK:
            # Anonymize/Redact
            return self._masker.redact(text, results)
            
        return text
