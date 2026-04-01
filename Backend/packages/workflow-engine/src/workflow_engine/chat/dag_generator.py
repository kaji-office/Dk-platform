import json
import logging
import dataclasses
from typing import Any
import os
from jinja2 import Environment, select_autoescape, FileSystemLoader

from workflow_engine.chat.models import RequirementSpec
from workflow_engine.cache.cached_llm import CachedLLMProvider
from workflow_engine.models import WorkflowDefinition
from workflow_engine.nodes.registry import NodeTypeRegistry, PortCompatibilityChecker
from workflow_engine.graph.builder import GraphBuilder
from workflow_engine.errors import WorkflowValidationError

logger = logging.getLogger(__name__)

class DAGGenerationError(Exception):
    pass

class DAGGeneratorService:
    def __init__(self, llm_provider: CachedLLMProvider):
        self.llm_provider = llm_provider
        self.env = Environment(
            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "prompts")),
            autoescape=select_autoescape()
        )
        
    async def generate(self, spec: RequirementSpec) -> WorkflowDefinition:
        """
        Generates a valid WorkflowDefinition DAG from spec.
        Retries up to 1 time if the output is invalid JSON, cyclic, or has port mismatches.
        """
        template = self.env.get_template("dag_generation.jinja2")
        
        # Build catalog details
        catalog = {}
        for node_type in NodeTypeRegistry.all_registered().keys():
            ports = PortCompatibilityChecker.get_output_ports(node_type)
            catalog[node_type] = ports if ports else ["default"]

        import dataclasses
        spec_dict = dataclasses.asdict(spec)
        prompt = template.render(
            spec=json.dumps(spec_dict, indent=2),
            catalog=catalog,
            error_context="",
        )
        
        # Attempt Generation
        return await self._attempt_generation(prompt, template, spec_dict, catalog, retry_attempt=0)

    async def _attempt_generation(self, prompt: str, template: Environment, spec_dict: dict, catalog: dict, retry_attempt: int) -> WorkflowDefinition:
        try:
            raw_response = await self.llm_provider.complete(prompt, temperature=0.2)
            
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            # 1. Parse JSON into WorkflowDefinition
            workflow_data = json.loads(cleaned)
            workflow = WorkflowDefinition(**workflow_data)
            
            # 2. Add ui_metadata tag
            if not hasattr(workflow, "ui_metadata"):
                workflow.ui_metadata = {}
            workflow.ui_metadata["generated_by_chat"] = True
            
            # 3. Validate DAG (Node registry + Acyclic + Port match)
            GraphBuilder.validate(workflow)
            
            return workflow
            
        except Exception as e:
            if retry_attempt >= 1:
                logger.error(f"Failed to generate DAG after retries: {e}\nRaw={raw_response if 'raw_response' in locals() else ''}")
                raise DAGGenerationError(f"DAG LLM generation failed: {str(e)}") from e
                
            error_msg = str(e)
            logger.warning(f"DAG generation failed once, retrying. Reason: {error_msg}")
            
            prompt = template.render(
                spec=json.dumps(spec_dict, indent=2),
                catalog=catalog,
                error_context=error_msg,
            )
            # Second attempt, no cache to ensure distinct outcome
            return await self._attempt_generation(prompt, template, spec_dict, catalog, retry_attempt=1)
