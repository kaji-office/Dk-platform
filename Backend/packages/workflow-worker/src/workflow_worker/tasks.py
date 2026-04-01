"""
Celery Tasks for workflow execution, scheduling, and notifications.
"""
from celery.utils.log import get_task_logger
from workflow_worker.celery_app import app
from workflow_worker.dependencies import get_engine, run_async, ConnectionErrorRetryable
from workflow_engine.errors import WorkflowValidationError
import traceback

logger = get_task_logger(__name__)

TRANSIENT_ERRORS = (ConnectionErrorRetryable, TimeoutError, ConnectionRefusedError)

@app.task(
    bind=True,
    autoretry_for=TRANSIENT_ERRORS,
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    name="workflow_worker.tasks.execute_workflow"
)
def execute_workflow(self, run_id: str, tenant_id: str):
    """AC: Calls ExecutionEngine.run() equivalent"""
    try:
        sdk = run_async(get_engine())
        run = run_async(sdk["execution_repo"].get(tenant_id, run_id))
        if not run:
            logger.error(f"Run {run_id} not found")
            return False
            
        workflow = run_async(sdk["workflow_repo"].get(tenant_id, run.workflow_id))
        if not workflow:
            logger.error(f"Workflow {run.workflow_id} not found")
            return False

        # Actually execute!
        run_async(sdk["orchestrator"].run(
            workflow_def=workflow,
            run_id=run_id,
            tenant_id=tenant_id,
            trigger_input=run.trigger_input
        ))
    except WorkflowValidationError as exc:
        logger.error(f"Validation error running execution {run_id}: {exc}")
        self.request.chain = None
        handle_dlq("execute_workflow", [run_id, tenant_id], {"exc": str(exc), "trace": traceback.format_exc()})
        return False
    except TRANSIENT_ERRORS as exc:
        logger.warning(f"Transient error running execution {run_id}: {exc}. Retrying...")
        raise exc
    except Exception as exc:
        logger.exception(f"Unexpected error running execution {run_id}: {exc}")
        handle_dlq("execute_workflow", [run_id, tenant_id], {"exc": str(exc), "trace": traceback.format_exc()})
        raise exc

@app.task(
    bind=True,
    autoretry_for=TRANSIENT_ERRORS,
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
    name="workflow_worker.tasks.execute_node"
)
def execute_node(self, run_id: str, node_id: str, tenant_id: str):
    try:
        sdk = run_async(get_engine())
        logger.info(f"Executing node {node_id} for run {run_id}")
        
        # Node execution is natively orchestrated via asyncio.gather() in RunOrchestrator.run()
        # This celery task remains for targeted single-node retries or heavy offloading.
        run_async(sdk["orchestrator"]._process_node(node_id=node_id, run_id=run_id, tenant_id=tenant_id))
    except WorkflowValidationError as exc:
        handle_dlq("execute_node", [run_id, node_id, tenant_id], {"exc": str(exc)})
        return False
    except TRANSIENT_ERRORS as exc:
        raise exc

@app.task(
    bind=True,
    name="workflow_worker.tasks.fire_schedule"
)
def fire_schedule(self):
    sdk = run_async(get_engine())
    from workflow_engine.scheduler.service import SchedulerService
    service = SchedulerService(sdk["scheduler"])
    
    fired = run_async(service.tick())
    logger.info(f"Checked schedules. Fired {len(fired)} schedules.")

@app.task(
    bind=True,
    autoretry_for=TRANSIENT_ERRORS,
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    name="workflow_worker.tasks.send_notification"
)
def send_notification(self, type: str, content: dict, recipient: str):
    # Dummy integration processing since Notification Port is not fully specified.
    logger.info(f"Dispatching async notification {type} to {recipient} with content: {content}")
    # In a real implementation this hooks to SES / Twilio / Slack webhooks.

@app.task(name="workflow_worker.tasks.dead_letter_queue")
def handle_dlq(failed_task_name: str, args: list, kwargs: dict):
    logger.error(f"DLQ Hit: Task {failed_task_name} failed. Args: {args}")
    sdk = run_async(get_engine())
    if sdk.get("audit"):
        run_async(sdk["audit"].create("SYSTEM", "task.failed", {
            "task": failed_task_name,
            "args": args,
            "kwargs": kwargs
        }))
