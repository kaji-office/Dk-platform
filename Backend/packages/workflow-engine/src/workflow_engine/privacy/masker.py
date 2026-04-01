"""
PIIMasker - Replaces PII with uniform [MASKED] placeholder.

Per D-4 acceptance criteria: SCAN_MASK replaces email/phone/SSN with `[MASKED]`.
"""
import logging

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_analyzer import RecognizerResult

logger = logging.getLogger("dk.privacy.masker")

# Standard replacement token per platform policy
MASK_TOKEN = "[MASKED]"


class PIIMasker:
    """Uses Presidio Anonymizer to replace PII entities with [MASKED]."""

    def __init__(self) -> None:
        try:
            self._anonymizer = AnonymizerEngine()
        except Exception as e:
            logger.error(f"Failed to initialize Anonymizer: {e}")
            self._anonymizer = None

    def redact(self, text: str, analyzer_results: list[RecognizerResult]) -> str:
        """
        Replace all PII entities with uniform [MASKED] placeholder.
        Every entity type (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, etc.)
        becomes '[MASKED]' per platform GDPR policy.
        """
        if not text or not self._anonymizer or not analyzer_results:
            return text

        try:
            # Build per-entity-type operator config map pointing all to "replace" with [MASKED]
            entity_types = {r.entity_type for r in analyzer_results}
            operators = {
                entity: OperatorConfig("replace", {"new_value": MASK_TOKEN})
                for entity in entity_types
            }

            result = self._anonymizer.anonymize(
                text=text,
                analyzer_results=analyzer_results,
                operators=operators
            )
            return result.text
        except Exception as e:
            logger.error(f"Anonymization failed, returning original text safely: {e}")
            return text
