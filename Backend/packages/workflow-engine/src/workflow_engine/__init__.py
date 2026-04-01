"""
workflow-engine — AI Workflow Builder Core SDK
=============================================

This is the product. API, Worker, and CLI are delivery mechanisms.

Usage:
    from workflow_engine import EngineConfig, WorkflowDefinition, RunOrchestrator
"""

__version__ = "1.0.0"

# Public API — consumers import only from here.
# Internal modules are NOT part of the public contract.

from workflow_engine.config import EngineConfig  # noqa: F401 (re-export)
