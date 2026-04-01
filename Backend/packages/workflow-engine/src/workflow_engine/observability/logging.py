"""
Structured JSON Logger for production tracking.
Hooks into `python-json-logger` to format logs for fluentd/DataDog out-of-the-box.
"""
import logging
import sys
from pythonjsonlogger import jsonlogger

def configure_structured_logging(level: int = logging.INFO) -> None:
    """
    Sets up the global root logger to emit everything as JSON.
    This enables Celery worker output to stream into ELK or Datadog perfectly cleanly
    with standard attributes 'timestamp', 'level', 'name', 'message'.
    """
    # Create the root logger
    root_logger = logging.getLogger()
    
    # If handlers already exist (like pytest), we might want to preserve them or wipe them.
    # For a cleanly managed worker, we clear existing ones.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    root_logger.setLevel(level)
    
    # Stream Handler to Stdout
    log_handler = logging.StreamHandler(sys.stdout)
    
    # We define the default JSON format string including commonly desired fields
    format_str = '%(timestamp)s %(levelname)s %(name)s %(message)s'
    
    # The JSON formatter converts these placeholders into structured JSON keys
    formatter = jsonlogger.JsonFormatter(
        format_str,
        rename_fields={"levelname": "level", "asctime": "timestamp"}
    )
    
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)
    
    # Internal DK Platform SDK logger specific configurations
    dk_logger = logging.getLogger("dk")
    dk_logger.setLevel(level)
    
def get_logger(name: str) -> logging.Logger:
    """Helper to get a named logger strictly."""
    return logging.getLogger(name)


class ExecutionLoggerAdapter(logging.LoggerAdapter):
    """
    Automatically injects `run_id` and `tenant_id` into every log record
    so that all log lines for an execution can be correlated.
    Satisfies D-5 acceptance criteria: 'run_id appears in all log lines'.
    """

    def process(self, msg: str, kwargs: dict) -> tuple:
        extra = kwargs.setdefault("extra", {})
        extra.update(self.extra)
        return msg, kwargs


def get_execution_logger(name: str, run_id: str, tenant_id: str) -> ExecutionLoggerAdapter:
    """
    Returns a LoggerAdapter that injects run_id and tenant_id into all log records.

    Usage:
        logger = get_execution_logger("dk.orchestrator", run_id="r-123", tenant_id="t-abc")
        logger.info("Node started")  # -> {"run_id": "r-123", "tenant_id": "t-abc", ...}
    """
    base_logger = logging.getLogger(name)
    return ExecutionLoggerAdapter(base_logger, {"run_id": run_id, "tenant_id": tenant_id})
