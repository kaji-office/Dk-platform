"""
Connectors public API — auto-registers all built-in connectors on import.
"""
from workflow_engine.integrations.connectors.base import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorRequestError,
)
from workflow_engine.integrations.connectors.registry import (
    ConnectorFactory,
    register_connector,
    get_connector_class,
    list_connectors,
)
from workflow_engine.integrations.connectors.slack import SlackConnector
from workflow_engine.integrations.connectors.email import EmailConnector
from workflow_engine.integrations.connectors.github import GitHubConnector

# Auto-register built-in connectors
register_connector(SlackConnector)
register_connector(EmailConnector)
register_connector(GitHubConnector)

__all__ = [
    "BaseConnector",
    "ConnectorAuthError",
    "ConnectorRequestError",
    "ConnectorFactory",
    "register_connector",
    "get_connector_class",
    "list_connectors",
    "SlackConnector",
    "EmailConnector",
    "GitHubConnector",
]
