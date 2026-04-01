"""
PIIDetector - Uses Microsoft Presidio Analyzer to find PII entities in text.
"""
import logging
from typing import Any

from presidio_analyzer import AnalyzerEngine, RecognizerResult

logger = logging.getLogger("dk.privacy.detector")

class PIIDetector:
    """Wrapper around Presidio Analyzer."""

    def __init__(self) -> None:
        try:
            # en_core_web_lg should be downloaded by pip
            self._analyzer = AnalyzerEngine()
        except Exception as e:
            logger.error(f"Failed to initialize Presidio Analyzer: {e}")
            self._analyzer = None

    def analyze(self, text: str, language: str = "en") -> list[RecognizerResult]:
        """
        Analyze a given string for PII.
        """
        if not text or not self._analyzer:
            return []
            
        try:
            return self._analyzer.analyze(text=text, entities=None, language=language)
        except Exception as e:
            logger.warning(f"Presidio analysis failed: {e}")
            return []
            
    def contains_pii(self, text: str, language: str = "en") -> bool:
        """Returns True if any PII was detected."""
        results = self.analyze(text, language)
        return len(results) > 0
