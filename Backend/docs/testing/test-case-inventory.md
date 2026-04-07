# Test Case Inventory
## DK Platform — All Packages
**Generated:** 2026-04-07 | **Total tests:** 451

---

## Summary

| Package | Test Files | Tests |
|---|---|---|
| `workflow-engine` | 25 | 307 |
| `workflow-api` | 8 | 110 |
| `workflow-worker` | 2 | 13 |
| `workflow-cli` | 2 | 21 |
| **Total** | **37** | **451** |

---

## workflow-engine (307 tests)

### `packages/workflow-engine/tests/test_errors.py` — 5 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_base_error_to_dict` | Base error to dict |
| 2 | `test_workflow_not_found_error` | Workflow not found error |
| 3 | `test_node_execution_error` | Node execution error |
| 4 | `test_connector_error` | Connector error |
| 5 | `test_other_errors` | Other errors |

### `packages/workflow-engine/tests/test_models.py` — 5 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_node_definition_validation` | Node definition validation |
| 2 | `test_workflow_definition_validation` | Workflow definition validation |
| 3 | `test_execution_run_validation` | Execution run validation |
| 4 | `test_tenant_config_validation` | Tenant config validation |
| 5 | `test_user_model_validation` | User model validation |

### `packages/workflow-engine/tests/integration/test_chat_mongo.py` — 1 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_mongo_conversation_repo_lifecycle` | Mongo conversation repo lifecycle |

### `packages/workflow-engine/tests/integration/test_human_in_loop.py` — 3 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_resume_delivers_human_response_to_downstream` | Full HITL flow: |
| 2 | `test_resume_on_non_waiting_run_raises` | resume() on a RUNNING run must raise NodeExecutionError |
| 3 | `test_resume_on_missing_run_raises` | resume() on a non-existent run must raise NodeExecutionError |

### `packages/workflow-engine/tests/integration/test_parallel_execution.py` — 4 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_all_parallel_nodes_succeed_single_run` | Single run with 10 parallel nodes — all must reach SUCCESS status |
| 2 | `test_parallel_nodes_no_state_overwrite_multiple_runs` | 50 concurrent runs, each with 10 parallel nodes |
| 3 | `test_bulk_update_node_states_atomicity` | Unit test: InMemoryExecutionRepo.bulk_update_node_states writes all nodes |
| 4 | `test_single_layer_batch_write_reduces_repo_calls` | Verify that for a layer of N parallel nodes, bulk_update_node_states |

### `packages/workflow-engine/tests/integration/test_storage.py` — 2 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_postgres_tenant_crud` | Postgres tenant crud |
| 2 | `test_mongo_execution_crud` | Mongo execution crud |

### `packages/workflow-engine/tests/test_auth/test_auth.py` — 20 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_jwt_access_token` | Jwt access token |
| 2 | `test_jwt_refresh_token` | Jwt refresh token |
| 3 | `test_jwt_rotate_refresh_token` | Jwt rotate refresh token |
| 4 | `test_jwt_expired_token` | Jwt expired token |
| 5 | `test_jwt_invalid_token` | Jwt invalid token |
| 6 | `test_password_hash_and_verify` | Password hash and verify |
| 7 | `test_password_strength` | Password strength |
| 8 | `test_api_key_create` | Api key create |
| 9 | `test_api_key_invalid_scope` | Api key invalid scope |
| 10 | `test_api_key_verify` | Api key verify |
| 11 | `test_api_key_check_scope` | Api key check scope |
| 12 | `test_mfa_setup_and_verify` | Mfa setup and verify |
| 13 | `test_mfa_backup_codes` | Mfa backup codes |
| 14 | `test_rbac_check` | Rbac check |
| 15 | `test_rbac_require` | Rbac require |
| 16 | `test_rbac_decorator_async` | Rbac decorator async |
| 17 | `test_rbac_decorator_sync` | Rbac decorator sync |
| 18 | `test_oauth_get_auth_url` | Oauth get auth url |
| 19 | `test_oauth_exchange_code` | Oauth exchange code |
| 20 | `test_oauth_refresh_token` | Oauth refresh token |

### `packages/workflow-engine/tests/test_billing/test_billing.py` — 9 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_llm_pricing_registry_known_model` | Llm pricing registry known model |
| 2 | `test_llm_pricing_registry_unknown_fallback` | Llm pricing registry unknown fallback |
| 3 | `test_cost_calculator_compute_cost` | Cost calculator compute cost |
| 4 | `test_cost_calculator_node_cost` | Cost calculator node cost |
| 5 | `test_quota_checker_enforces_limit` | Quota checker enforces limit |
| 6 | `test_usage_recorder_node_completed` | Usage recorder node completed |
| 7 | `test_usage_recorder_llm_completed` | Usage recorder llm completed |
| 8 | `test_billing_aggregator_no_data` | Billing aggregator no data |
| 9 | `test_billing_aggregator_sums_data` | Billing aggregator sums data |

### `packages/workflow-engine/tests/test_cache/test_cache.py` — 32 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_set_and_get` | Set and get |
| 2 | `test_set_with_ttl_calls_setex` | Set with ttl calls setex |
| 3 | `test_get_miss_returns_none` | Get miss returns none |
| 4 | `test_get_on_redis_error_returns_none_gracefully` | Get on redis error returns none gracefully |
| 5 | `test_set_on_redis_error_does_not_raise` | Set on redis error does not raise |
| 6 | `test_delete_on_error_does_not_raise` | Delete on error does not raise |
| 7 | `test_delete_removes_key` | Delete removes key |
| 8 | `test_key_prefix_applied` | Key prefix applied |
| 9 | `test_get_bytes_decoded_to_str` | Get bytes decoded to str |
| 10 | `test_build_is_deterministic` | Same inputs must always produce the same key |
| 11 | `test_build_different_prompts_produce_different_keys` | Build different prompts produce different keys |
| 12 | `test_build_different_params_produce_different_keys` | Build different params produce different keys |
| 13 | `test_build_params_dict_order_independent` | Params must be hashed deterministically regardless of dict key order |
| 14 | `test_build_cross_tenant_isolation` | Keys for same prompt/model must differ across tenants |
| 15 | `test_build_contains_all_components` | Build contains all components |
| 16 | `test_build_semantic_shorter_key` | Build semantic shorter key |
| 17 | `test_model_with_slashes_sanitised` | Model with slashes sanitised |
| 18 | `test_cache_hit_above_threshold` | get() must return response when similarity >= threshold |
| 19 | `test_cache_miss_below_threshold` | get() must return None when similarity < threshold |
| 20 | `test_cache_miss_no_rows` | get() must return None when no rows in DB |
| 21 | `test_threshold_configurable` | Lower threshold allows a wider similarity window |
| 22 | `test_get_on_db_error_returns_none` | Get on db error returns none |
| 23 | `test_set_calls_db_upsert` | Set calls db upsert |
| 24 | `test_set_on_error_does_not_raise` | Set on error does not raise |
| 25 | `test_purge_expired_returns_count` | Purge expired returns count |
| 26 | `test_redis_hit_does_not_call_provider` | If Redis has a cached response, provider.complete() must NOT be called |
| 27 | `test_cache_miss_calls_provider` | On cache miss, provider.complete() must be called exactly once |
| 28 | `test_cache_miss_writes_to_redis` | On provider call, response must be written to Redis |
| 29 | `test_second_call_hits_redis_not_provider` | Second identical call must read from Redis without calling provider |
| 30 | `test_semantic_hit_does_not_call_provider` | Semantic cache hit must also prevent calling provider.complete() |
| 31 | `test_redis_error_falls_through_to_provider` | If Redis throws, provider must still be called (no propagated exception) |
| 32 | `test_embed_delegates_to_provider` | embed() should pass through to the underlying provider |

### `packages/workflow-engine/tests/test_connectors/test_connectors.py` — 23 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_slack_is_base_connector` | Slack is base connector |
| 2 | `test_email_is_base_connector` | Email is base connector |
| 3 | `test_github_is_base_connector` | Github is base connector |
| 4 | `test_slack_missing_token_raises_auth_error` | Slack missing token raises auth error |
| 5 | `test_email_missing_api_key_raises_auth_error` | Email missing api key raises auth error |
| 6 | `test_github_missing_token_raises_auth_error` | Github missing token raises auth error |
| 7 | `test_slack_check_health` | Slack check health |
| 8 | `test_slack_send_message` | Slack send message |
| 9 | `test_slack_send_dm` | Slack send dm |
| 10 | `test_slack_create_channel` | Slack create channel |
| 11 | `test_connector_request_error_on_4xx` | Connector request error on 4xx |
| 12 | `test_email_send_email` | Email send email |
| 13 | `test_email_send_template` | Email send template |
| 14 | `test_github_check_health` | Github check health |
| 15 | `test_github_create_issue` | Github create issue |
| 16 | `test_github_create_pr` | Github create pr |
| 17 | `test_github_list_repos` | Github list repos |
| 18 | `test_connector_factory_caches_instance` | ConnectorFactory must return same instance on repeated get() calls |
| 19 | `test_connector_factory_separate_per_tenant` | Different tenants must get separate connector instances |
| 20 | `test_register_connector_decorator` | register_connector() must make connector discoverable by name |
| 21 | `test_get_connector_class_returns_correct_type` | Get connector class returns correct type |
| 22 | `test_get_connector_class_raises_for_unknown` | Get connector class raises for unknown |
| 23 | `test_close_all_cleans_cache` | close_all() must disconnect and clear the factory cache |

### `packages/workflow-engine/tests/test_execution/test_engine.py` — 8 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_state_machine_valid_transition` | State machine valid transition |
| 2 | `test_state_machine_invalid_transition` | State machine invalid transition |
| 3 | `test_pii_scanner_block_ssn` | Pii scanner block ssn |
| 4 | `test_pii_scanner_allow` | Pii scanner allow |
| 5 | `test_retry_handler` | Retry handler |
| 6 | `test_timeout_manager` | Timeout manager |
| 7 | `test_context_manager_inline` | Context manager inline |
| 8 | `test_context_manager_blob` | Context manager blob |

### `packages/workflow-engine/tests/test_execution/test_engine_integration.py` — 9 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_orchestrator_full_run` | Orchestrator full run |
| 2 | `test_orchestrator_max_depth` | Orchestrator max depth |
| 3 | `test_orchestrator_empty_graph` | Orchestrator empty graph |
| 4 | `test_orchestrator_cancel_mid_run` | Orchestrator cancel mid run |
| 5 | `test_orchestrator_pii_blocked` | Orchestrator pii blocked |
| 6 | `test_orchestrator_node_exception` | Orchestrator node exception |
| 7 | `test_orchestrator_cancel_and_resume` | Orchestrator cancel and resume |
| 8 | `test_orchestrator_resume_invalid` | Orchestrator resume invalid |
| 9 | `test_get_node_def_missing` | Get node def missing |

### `packages/workflow-engine/tests/test_execution/test_orchestration_flow.py` — 42 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_trigger_passes_input_to_downstream` | ManualTriggerNode wraps input as payload; CodeExecutionNode reads it |
| 2 | `test_output_data_set_on_final_node` | output_data on the run should reflect the last node's outputs |
| 3 | `test_three_node_chain` | A → B → C: each node transforms the value |
| 4 | `test_non_executable_node_skipped` | NoteNode is not executable — it must be silently skipped |
| 5 | `test_parallel_branches_both_succeed` | Two independent code nodes in the same layer both execute |
| 6 | `test_one_parallel_branch_failure_fails_run` | If one parallel branch fails, the run ends as FAILED |
| 7 | `test_bulk_update_called_once_per_layer` | Performance contract: batch DB write must happen once per topo layer, |
| 8 | `test_branch_routes_to_true_port` | When condition is met, ControlFlowNode emits on the 'true' port |
| 9 | `test_switch_routes_to_correct_case` | SWITCH mode picks the port matching the switch_field value |
| 10 | `test_node_runtime_exception_fails_run` | Unhandled Python exception inside a node → run.status == FAILED |
| 11 | `test_zero_division_error` | Zero division error |
| 12 | `test_sandbox_blocks_os_import` | CodeExecutionNode's AST scanner blocks 'import os' before execution |
| 13 | `test_node_timeout_fails_run` | A node that exceeds timeout_seconds raises SandboxTimeoutError → run FAILED |
| 14 | `test_missing_node_def_raises` | _get_node_def raises NodeExecutionError for a node_id not in the workflow |
| 15 | `test_scan_block_policy_fails_run` | SCAN_BLOCK: PII in trigger input must fail the run immediately |
| 16 | `test_scan_warn_policy_continues_run` | SCAN_WARN: PII scanner does not raise → run continues to SUCCESS |
| 17 | `test_disabled_policy_skips_scan` | DISABLED: PIIScanner.scan_dict should never be called |
| 18 | `test_cancel_before_start_stops_execution` | If the run is marked CANCELLED before the first node's repo.get() returns, |
| 19 | `test_cancel_between_nodes` | Run is cancelled after the first node completes. The second node should |
| 20 | `test_cancel_method_sets_status` | orchestrator.cancel() must transition run to CANCELLED in the repo |
| 21 | `test_human_gate_pauses_run` | A node returning metadata.status == WAITING_HUMAN must pause the run |
| 22 | `test_resume_from_waiting_human_succeeds` | After a run is paused at WAITING_HUMAN, calling resume() with a human |
| 23 | `test_resume_on_non_waiting_run_raises` | Calling resume() on a RUNNING run must raise NodeExecutionError |
| 24 | `test_resume_with_descendants_continues_dag` | After a human gate, resume() builds a sub-workflow of all descendants |
| 25 | `test_node_state_events_published` | node_state events must be published for each node that runs |
| 26 | `test_run_complete_event_published_on_success` | run_complete event must be published when the DAG finishes |
| 27 | `test_no_redis_does_not_raise` | Orchestrator without Redis must run without error (graceful no-op) |
| 28 | `test_redis_publish_failure_does_not_fail_run` | A Redis publish error must be swallowed — the run must still succeed |
| 29 | `test_transient_error_retried_then_succeeds` | A node that fails once then succeeds should complete the run as SUCCESS |
| 30 | `test_sandbox_timeout_not_retried` | SandboxTimeoutError is in non_retryable — must fail on first attempt |
| 31 | `test_exhausted_retries_raise_final_error` | After max_attempts, the last exception must propagate |
| 32 | `test_queued_to_running_allowed` | Queued to running allowed |
| 33 | `test_running_to_success_allowed` | Running to success allowed |
| 34 | `test_success_to_running_blocked` | Terminal state SUCCESS must not allow transition back to RUNNING |
| 35 | `test_waiting_human_to_running_allowed` | Resume path: WAITING_HUMAN → RUNNING must be a valid transition |
| 36 | `test_normal_execution_calls_orchestrator_run` | execute_workflow task must call orchestrator.run() with the run's input_data |
| 37 | `test_resume_path_calls_orchestrator_resume` | When resume_node is supplied, execute_workflow must call orchestrator.resume() |
| 38 | `test_validation_error_goes_to_dlq_not_retry` | WorkflowValidationError must not trigger a retry — goes straight to DLQ |
| 39 | `test_empty_workflow_succeeds` | An empty workflow (no nodes) completes as SUCCESS immediately |
| 40 | `test_max_depth_exceeded_raises` | Recursive sub-workflows beyond max_depth must raise NodeExecutionError |
| 41 | `test_multiple_runs_are_tenant_isolated` | Two runs for different tenants using the same repo must not see each other's state |
| 42 | `test_preloaded_outputs_available_to_downstream` | preloaded_outputs (used on resume) should be accessible by downstream |

### `packages/workflow-engine/tests/test_execution/test_pii_scanning.py` — 13 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_ssn_blocked` | Ssn blocked |
| 2 | `test_credit_card_blocked` | Credit card blocked |
| 3 | `test_nested_dict_pii_blocked` | Nested dict pii blocked |
| 4 | `test_pii_in_list_blocked` | Pii in list blocked |
| 5 | `test_clean_data_not_blocked` | Clean data not blocked |
| 6 | `test_multiple_pii_fields_blocked_on_first_hit` | Multiple pii fields blocked on first hit |
| 7 | `test_ssn_does_not_raise_in_warn_mode` | Ssn does not raise in warn mode |
| 8 | `test_credit_card_does_not_raise_in_warn_mode` | Credit card does not raise in warn mode |
| 9 | `test_pii_ignored_when_disabled` | Pii ignored when disabled |
| 10 | `test_empty_dict_no_error` | Empty dict no error |
| 11 | `test_none_values_do_not_crash` | None values do not crash |
| 12 | `test_numeric_values_do_not_crash` | Numeric values do not crash |
| 13 | `test_empty_string_not_flagged` | Empty string not flagged |

### `packages/workflow-engine/tests/test_graph/test_builder_validator.py` — 12 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_build_adjacency_list_simple` | Build adjacency list simple |
| 2 | `test_build_adjacency_list_parallel` | Build adjacency list parallel |
| 3 | `test_topological_sort_linear` | Topological sort linear |
| 4 | `test_topological_sort_parallel_branches` | Topological sort parallel branches |
| 5 | `test_topological_sort_single_node` | Topological sort single node |
| 6 | `test_valid_linear_graph` | Valid linear graph |
| 7 | `test_cycle_detection_simple_cycle` | Cycle detection simple cycle |
| 8 | `test_cycle_detection_self_loop` | Cycle detection self loop |
| 9 | `test_cycle_detection_longer_cycle` | Cycle detection longer cycle |
| 10 | `test_invalid_edge_source` | Invalid edge source |
| 11 | `test_invalid_edge_target` | Invalid edge target |
| 12 | `test_dag_no_cycle` | Dag no cycle |

### `packages/workflow-engine/tests/test_mcp/test_mcp.py` — 16 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_mcp_client_context_manager` | MCPClient must connect on __aenter__ and disconnect on __aexit__ |
| 2 | `test_mcp_client_list_tools` | list_tools() must return structured tool descriptors |
| 3 | `test_mcp_client_call_tool` | call_tool() must invoke the session and return content |
| 4 | `test_mcp_client_call_tool_not_connected` | call_tool() must raise RuntimeError if not connected |
| 5 | `test_mcp_client_list_tools_not_connected` | list_tools() must raise RuntimeError if not connected |
| 6 | `test_registry_reuses_pooled_connection` | MCPClientRegistry must not reconnect on second get() for same server |
| 7 | `test_registry_separate_clients_per_tenant` | Different tenants must get separate pooled connections |
| 8 | `test_schema_cache_hit_on_second_call` | Second list_tools() call must return cached data without calling server |
| 9 | `test_schema_cache_ttl_expiry` | Schema cache must return None after TTL expires |
| 10 | `test_schema_cache_valid_before_ttl` | Schema cache must return data before TTL expires |
| 11 | `test_schema_cache_invalidate` | Invalidated cache entry must not be returned |
| 12 | `test_response_cache_hit` | call_tool() with cache_ttl must return cached result on second call |
| 13 | `test_response_cache_different_args_not_cached` | Different arguments must NOT share cache entries |
| 14 | `test_mcp_registry_raises_when_feature_disabled` | Registry must raise FeatureDisabledError when MCP_NODE_ENABLED=false |
| 15 | `test_mcp_registry_works_when_feature_enabled` | Registry must proceed normally when MCP_NODE_ENABLED=true |
| 16 | `test_registry_close_all` | close_all() must disconnect all pooled clients and clear the pool |

### `packages/workflow-engine/tests/test_nodes/test_nodes.py` — 49 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_all_17_registered` | All 17 registered |
| 2 | `test_get_known_type` | Get known type |
| 3 | `test_get_unknown_raises` | Get unknown raises |
| 4 | `test_is_registered` | Is registered |
| 5 | `test_valid_port` | Valid port |
| 6 | `test_note_node_cannot_be_source` | Note node cannot be source |
| 7 | `test_unknown_source_type_raises` | Unknown source type raises |
| 8 | `test_get_output_ports` | Get output ports |
| 9 | `test_calls_llm_and_returns_text` | Calls llm and returns text |
| 10 | `test_cache_hit_skips_llm` | Cache hit skips llm |
| 11 | `test_no_llm_raises` | No llm raises |
| 12 | `test_plain_text_response_exits_loop` | Plain text response exits loop |
| 13 | `test_tool_call_loop` | Tool call loop |
| 14 | `test_mcp_tools_fetched` | Mcp tools fetched |
| 15 | `test_no_llm_raises` | No llm raises |
| 16 | `test_basic_execution` | Basic execution |
| 17 | `test_ast_blocks_os_import` | Ast blocks os import |
| 18 | `test_ast_blocks_sys_import` | Ast blocks sys import |
| 19 | `test_syntax_error_raises` | Syntax error raises |
| 20 | `test_empty_code_returns_none` | Empty code returns none |
| 21 | `test_unsupported_method_raises` | Unsupported method raises |
| 22 | `test_successful_get_json` | Successful get json |
| 23 | `test_httpx_timeout_raises` | Httpx timeout raises |
| 24 | `test_renders_template` | Renders template |
| 25 | `test_custom_output_key` | Custom output key |
| 26 | `test_branch_true` | Branch true |
| 27 | `test_branch_false` | Branch false |
| 28 | `test_switch_matches` | Switch matches |
| 29 | `test_switch_default` | Switch default |
| 30 | `test_loop_fan_out` | Loop fan out |
| 31 | `test_merge_passthrough` | Merge passthrough |
| 32 | `test_invalid_mode_raises` | Invalid mode raises |
| 33 | `test_raises_when_disabled` | Raises when disabled |
| 34 | `test_calls_tool_and_returns` | Calls tool and returns |
| 35 | `test_missing_required_param_raises` | Missing required param raises |
| 36 | `test_result_cache_returns_without_calling_tool` | Result cache returns without calling tool |
| 37 | `test_is_not_executable` | Is not executable |
| 38 | `test_returns_empty_output` | Returns empty output |
| 39 | `test_extracts_value` | Extracts value |
| 40 | `test_is_terminal` | Is terminal |
| 41 | `test_stores_state` | Stores state |
| 42 | `test_manual_trigger_passes_payload` | Manual trigger passes payload |
| 43 | `test_manual_trigger_validates_schema` | Manual trigger validates schema |
| 44 | `test_scheduled_trigger_valid_cron` | Scheduled trigger valid cron |
| 45 | `test_scheduled_trigger_invalid_cron` | Scheduled trigger invalid cron |
| 46 | `test_integration_trigger_passes_payload` | Integration trigger passes payload |
| 47 | `test_missing_workflow_id_raises` | Missing workflow id raises |
| 48 | `test_executor_called` | Executor called |
| 49 | `test_no_executor_surfaces_intent` | No executor surfaces intent |

### `packages/workflow-engine/tests/test_nodes/test_nodes_missing.py` — 12 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_auth_basic_and_body` | Auth basic and body |
| 2 | `test_auth_oauth2` | Auth oauth2 |
| 3 | `test_request_error` | Request error |
| 4 | `test_no_llm_raises` | No llm raises |
| 5 | `test_empty_query_returns_empty` | Empty query returns empty |
| 6 | `test_embed_and_search` | Embed and search |
| 7 | `test_storage_malformed_json_fallback` | Storage malformed json fallback |
| 8 | `test_disabled` | Disabled |
| 9 | `test_empty_query` | Empty query |
| 10 | `test_search_results` | Search results |
| 11 | `test_search_cache_hit` | Search cache hit |
| 12 | `test_search_error` | Search error |

### `packages/workflow-engine/tests/test_observability/test_logging.py` — 1 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_json_structured_logging` | Json structured logging |

### `packages/workflow-engine/tests/test_observability/test_metrics.py` — 3 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_prometheus_workflow_metric` | Prometheus workflow metric |
| 2 | `test_prometheus_node_metric` | Prometheus node metric |
| 3 | `test_prometheus_llm_metric` | Prometheus llm metric |

### `packages/workflow-engine/tests/test_observability/test_observability.py` — 10 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_root_span_with_child_spans` | Every execution must emit a root span with child spans per node |
| 2 | `test_single_workflow_span_attributes` | Root span must carry run_id, tenant_id, and system attributes |
| 3 | `test_error_in_workflow_sets_error_span` | When a workflow raises, the root span must be in ERROR state |
| 4 | `test_node_tracer_error_span` | NodeTracer must record exception and set ERROR status |
| 5 | `test_run_id_in_all_log_lines` | run_id and tenant_id must appear in every log line for an execution |
| 6 | `test_standard_logger_structured_json` | Standard logger must emit valid JSON with level, name, message |
| 7 | `test_workflow_run_counter_increments` | Prometheus workflow run counter must increment correctly |
| 8 | `test_node_execution_histogram` | Node execution histogram must record count and duration |
| 9 | `test_llm_token_counter_input_output` | LLM token counter must separately track input and output tokens |
| 10 | `test_failed_workflow_counter` | Workflow failure status must be tracked distinctly from success |

### `packages/workflow-engine/tests/test_observability/test_tracing.py` — 3 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_tracing_workflow_decorator` | trace_workflow decorator must emit one span with correct attributes |
| 2 | `test_tracing_node_context` | NodeTracer context manager must emit one completed span |
| 3 | `test_tracing_node_exception` | NodeTracer must set ERROR status when an exception is raised |

### `packages/workflow-engine/tests/test_privacy/test_privacy.py` — 13 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_mask_email` | Mask email |
| 2 | `test_mask_person_name` | Mask person name |
| 3 | `test_mask_phone_number` | Mask phone number |
| 4 | `test_mask_multiple_entities_all_use_masked_token` | All entity types must resolve to [MASKED], not entity-typed tags like <EMAIL_ADDRESS> |
| 5 | `test_handler_scan_mask_policy` | PrivacyHandler with SCAN_MASK must apply [MASKED] via policy |
| 6 | `test_scan_block_raises_on_email` | SCAN_BLOCK must raise PIIBlockedError when email detected |
| 7 | `test_scan_block_raises_on_phone` | SCAN_BLOCK must raise for phone numbers |
| 8 | `test_scan_block_passes_clean_text` | SCAN_BLOCK must not raise on clean, PII-free text |
| 9 | `test_scan_warn_always_passes` | SCAN_WARN must never block, even on PII-heavy text |
| 10 | `test_delete_user_data_all_three_stores` | delete_user_data must purge MongoDB, PostgreSQL, and S3 |
| 11 | `test_delete_user_data_without_s3` | delete_user_data must succeed even if S3 not configured |
| 12 | `test_export_user_data` | export_user_data must collect records from MongoDB and Postgres |
| 13 | `test_false_positive_rate` | False-positive rate on clean technical log-line dataset must be < 5% |

### `packages/workflow-engine/tests/test_scheduler/test_scheduler.py` — 3 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_scheduler_register` | Scheduler register |
| 2 | `test_scheduler_deactivate` | Scheduler deactivate |
| 3 | `test_scheduler_tick` | Scheduler tick |

### `packages/workflow-engine/tests/test_storage/test_storage.py` — 9 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_mongo_workflow_create` | Mongo workflow create |
| 2 | `test_mongo_workflow_get` | Mongo workflow get |
| 3 | `test_mongo_execution_update` | Mongo execution update |
| 4 | `test_mongo_schedule_get_due` | Mongo schedule get due |
| 5 | `test_postgres_user_get` | Postgres user get |
| 6 | `test_postgres_tenant_update` | Postgres tenant update |
| 7 | `test_postgres_billing_record` | Postgres billing record |
| 8 | `test_s3_upload` | S3 upload |
| 9 | `test_s3_tenant_isolation_download` | S3 tenant isolation download |

## workflow-api (110 tests)

### `packages/workflow-api/tests/test_api.py` — 56 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_no_auth_header_returns_401` | No auth header returns 401 |
| 2 | `test_invalid_token_returns_401` | Invalid token returns 401 |
| 3 | `test_viewer_can_read_workflows` | Viewer can read workflows |
| 4 | `test_viewer_blocked_on_write` | Viewer blocked on write |
| 5 | `test_admin_allowed_on_write` | Admin allowed on write |
| 6 | `test_rate_limit_exceeded` | Rate limit exceeded |
| 7 | `test_websocket_lifecycle` | Websocket lifecycle |
| 8 | `test_health` | Health |
| 9 | `test_health_ready` | Health ready |
| 10 | `test_auth_register` | Auth register |
| 11 | `test_auth_login` | Auth login |
| 12 | `test_auth_logout` | Auth logout |
| 13 | `test_auth_token_refresh` | Auth token refresh |
| 14 | `test_auth_verify_email` | Auth verify email |
| 15 | `test_auth_password_reset_request` | Auth password reset request |
| 16 | `test_auth_password_reset` | Auth password reset |
| 17 | `test_auth_mfa_setup` | Auth mfa setup |
| 18 | `test_auth_mfa_verify` | Auth mfa verify |
| 19 | `test_auth_oauth_redirect` | Auth oauth redirect |
| 20 | `test_auth_oauth_callback` | Auth oauth callback |
| 21 | `test_users_me` | Users me |
| 22 | `test_users_me_patch` | Users me patch |
| 23 | `test_users_api_keys_list` | Users api keys list |
| 24 | `test_users_api_keys_create` | Users api keys create |
| 25 | `test_users_api_keys_delete` | Users api keys delete |
| 26 | `test_workflows_list` | Workflows list |
| 27 | `test_workflows_create` | Workflows create |
| 28 | `test_workflows_get` | Workflows get |
| 29 | `test_workflows_update` | Workflows update |
| 30 | `test_workflows_delete` | Workflows delete |
| 31 | `test_workflows_activate` | Workflows activate |
| 32 | `test_workflows_deactivate` | Workflows deactivate |
| 33 | `test_versions_list` | Versions list |
| 34 | `test_versions_get` | Versions get |
| 35 | `test_versions_restore` | Versions restore |
| 36 | `test_schedules_list` | Schedules list |
| 37 | `test_schedules_create` | Schedules create |
| 38 | `test_schedules_get` | Schedules get |
| 39 | `test_schedules_update` | Schedules update |
| 40 | `test_schedules_delete` | Schedules delete |
| 41 | `test_executions_trigger` | Executions trigger |
| 42 | `test_executions_list` | Executions list |
| 43 | `test_executions_get` | Executions get |
| 44 | `test_executions_cancel` | Executions cancel |
| 45 | `test_executions_retry` | Executions retry |
| 46 | `test_executions_nodes` | Executions nodes |
| 47 | `test_executions_human_input` | Executions human input |
| 48 | `test_executions_logs` | Executions logs |
| 49 | `test_webhooks_list` | Webhooks list |
| 50 | `test_webhooks_create` | Webhooks create |
| 51 | `test_webhooks_get` | Webhooks get |
| 52 | `test_webhooks_update` | Webhooks update |
| 53 | `test_webhooks_delete` | Webhooks delete |
| 54 | `test_webhooks_inbound` | Webhooks inbound |
| 55 | `test_audit_list` | Audit list |
| 56 | `test_usage_get` | Usage get |

### `packages/workflow-api/tests/test_cancellation.py` — 6 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_cancel_running_run_returns_cancelled` | POST /executions/{run_id}/cancel on a RUNNING run returns cancelled status |
| 2 | `test_cancel_calls_execution_service` | cancel endpoint must call execution_service.cancel() exactly once |
| 3 | `test_cancel_unauthenticated_returns_401` | cancel endpoint without auth must return 401 |
| 4 | `test_cancel_viewer_role_forbidden` | VIEWER role cannot cancel executions (→ 403) |
| 5 | `test_cancel_unknown_run_returns_404` | cancel on a run that doesn't exist must return 404 |
| 6 | `test_orchestrator_cancel_transitions_to_cancelled` | RunOrchestrator.cancel() must set run status to CANCELLED |

### `packages/workflow-api/tests/test_chat_api.py` — 7 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_create_session` | Create session |
| 2 | `test_get_session` | Get session |
| 3 | `test_list_sessions` | List sessions |
| 4 | `test_post_message` | Post message |
| 5 | `test_force_generate` | Force generate |
| 6 | `test_workflow_edit` | Workflow edit |
| 7 | `test_websocket_endpoint` | Websocket endpoint |

### `packages/workflow-api/tests/test_idempotency.py` — 3 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_same_idempotency_key_returns_same_run_id` | Two POST requests with the same Idempotency-Key must return identical run_id |
| 2 | `test_different_idempotency_keys_create_different_runs` | Two POST requests with different Idempotency-Keys must produce different run_ids |
| 3 | `test_no_idempotency_key_always_creates_new_run` | Requests without an Idempotency-Key header always create a new run |

### `packages/workflow-api/tests/test_perf_triggers.py` — 3 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_100_concurrent_triggers_all_succeed` | Fire 100 concurrent trigger requests; all must return 2xx within the deadline |
| 2 | `test_100_concurrent_triggers_all_unique_run_ids` | Without idempotency keys, every trigger must return a distinct run_id |
| 3 | `test_100_concurrent_triggers_service_called_100_times` | The execution service must be called exactly 100 times (no short-circuiting) |

### `packages/workflow-api/tests/test_perf_websocket.py` — 3 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_50_concurrent_ws_clients_all_connect` | 50 concurrent WebSocket connections must all be accepted (no rejection) |
| 2 | `test_50_ws_clients_receive_snapshot` | The initial snapshot (existing node_states) must be delivered to every client |
| 3 | `test_ws_fallback_polling_under_load` | When redis_client is None (fallback mode), 50 concurrent clients should still |

### `packages/workflow-api/tests/test_ws_streaming.py` — 9 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_no_token_closes_4001` | WS connect without ?token= → server closes with 4001 |
| 2 | `test_invalid_token_closes_4001` | WS connect with bad token → server closes with 4001 |
| 3 | `test_run_not_found_sends_error` | If run_id doesn't exist, WS sends error JSON then closes |
| 4 | `test_already_terminal_run_sends_snapshot_and_complete` | Client connects to a run that already succeeded |
| 5 | `test_snapshot_contains_all_completed_nodes` | Snapshot message includes all pre-existing node states |
| 6 | `test_node_state_event_delivered_from_pubsub` | Redis PubSub publishes a node_state event |
| 7 | `test_connection_closes_after_run_complete` | WS connection must close once run_complete is received |
| 8 | `test_fallback_polling_delivers_node_state_events` | When no Redis client is available, WS falls back to polling |
| 9 | `test_waiting_human_event_forwarded` | PubSub run_waiting_human event is forwarded to the WS client |

### `packages/workflow-api/tests/security/test_auth.py` — 23 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_no_auth_header_rejected` | Request with no Authorization header must return 401 |
| 2 | `test_deactivated_user_rejected` | verify_token raising an error (e.g., deactivated user) must return 401 |
| 3 | `test_invalid_token_rejected` | verify_token raising InvalidTokenError must return 401 |
| 4 | `test_expired_token_rejected` | verify_token raising TokenExpiredError must return 401 |
| 5 | `test_viewer_cannot_delete_workflow` | A VIEWER-role user must not be able to delete a workflow (→ 403) |
| 6 | `test_viewer_cannot_trigger_execution` | A VIEWER-role user must not be able to trigger an execution (→ 403) |
| 7 | `test_cross_tenant_workflow_returns_404` | Authenticated user from tenant-A must get 404 when accessing a workflow |
| 8 | `test_cross_tenant_execution_returns_404` | User from tenant-A accessing tenant-B's execution must get 404 |
| 9 | `test_duplicate_email_registration` | Registering the same email twice must return 422 (conflict) |
| 10 | `test_tampered_jwt_rejected` | Flipping one byte in the JWT signature must raise InvalidTokenError |
| 11 | `test_access_token_as_refresh_rejected` | Using an access token where a refresh token is expected must fail |
| 12 | `test_refresh_token_as_access_rejected` | Using a refresh token as an access token must fail |
| 13 | `test_expired_access_token_rejected` | A token with exp in the past must raise TokenExpiredError |
| 14 | `test_wrong_audience_rejected` | Token with wrong audience claim must be rejected |
| 15 | `test_wrong_issuer_rejected` | Token with wrong issuer claim must be rejected |
| 16 | `test_valid_access_token_accepted` | Freshly issued access token must verify without error |
| 17 | `test_valid_refresh_token_accepted` | Freshly issued refresh token must verify without error |
| 18 | `test_viewer_cannot_satisfy_editor_requirement` | Viewer cannot satisfy editor requirement |
| 19 | `test_admin_satisfies_editor_requirement` | Admin satisfies editor requirement |
| 20 | `test_superadmin_satisfies_all_roles` | Superadmin satisfies all roles |
| 21 | `test_empty_roles_rejected_for_any_requirement` | Empty roles rejected for any requirement |
| 22 | `test_check_returns_false_for_insufficient_role` | Check returns false for insufficient role |
| 23 | `test_check_returns_true_for_sufficient_role` | Check returns true for sufficient role |

## workflow-worker (13 tests)

### `packages/workflow-worker/tests/test_stale_run_reaper.py` — 7 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_stale_running_run_marked_failed` | A RUNNING run older than 15 min must be marked FAILED |
| 2 | `test_fresh_running_run_not_reaped` | A RUNNING run less than 15 min old must NOT be reaped |
| 3 | `test_terminal_runs_not_returned_by_list_stale` | SUCCESS/FAILED/CANCELLED runs must not appear in list_stale_running |
| 4 | `test_mixed_runs_only_stale_reaped` | Only the stale RUNNING run is reaped when mixed runs exist |
| 5 | `test_celery_task_revoked_on_reap` | A stale run with a stored celery_task_id should have its Celery task |
| 6 | `test_exactly_at_boundary_not_reaped` | A run started exactly at the 15-min boundary should not be reaped |
| 7 | `test_empty_repo_reap_is_noop` | reap_stale_runs on empty repo should not crash |

### `packages/workflow-worker/tests/test_worker.py` — 6 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_graceful_drain_config` | Graceful drain config |
| 2 | `test_no_retry_on_workflow_validation_error` | No retry on workflow validation error |
| 3 | `test_retry_on_connection_error` | Retry on connection error |
| 4 | `test_beat_schedule_configured` | Beat schedule configured |
| 5 | `test_fire_schedule_execution` | Fire schedule execution |
| 6 | `test_handle_dlq_logs_to_audit` | Handle dlq logs to audit |

## workflow-cli (21 tests)

### `packages/workflow-cli/tests/test_cli.py` — 4 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_config_path_ac` | AC: Config stored in ~/.config/wf/config.toml |
| 2 | `test_run_trigger_success_exit_0` | AC: wf run trigger <workflow_id> exits 0 on QUEUED |
| 3 | `test_run_trigger_error_exit_1` | AC: wf run trigger <workflow_id> exits 1 on error |
| 4 | `test_run_logs_follow` | AC: wf run logs <run_id> --follow streams logs to stdout |

### `packages/workflow-cli/tests/test_cli_integration.py` — 17 tests

| # | Test Function | Description |
|---|---|---|
| 1 | `test_auth_login_success` | Successful login stores token and prints success message |
| 2 | `test_auth_login_wrong_password` | Wrong credentials (401) prints human-readable error |
| 3 | `test_auth_whoami_with_token` | whoami with a valid token prints user info |
| 4 | `test_auth_whoami_not_logged_in` | whoami without a token prints login prompt |
| 5 | `test_workflow_list` | workflow list renders table with workflow entries |
| 6 | `test_workflow_create` | workflow create prints success and new workflow id |
| 7 | `test_workflow_update_patch` | workflow update patches the workflow and confirms the new name |
| 8 | `test_workflow_activate` | workflow activate sets is_active=True and confirms |
| 9 | `test_workflow_deactivate` | workflow deactivate sets is_active=False and confirms |
| 10 | `test_workflow_delete` | workflow delete calls DELETE and exits 0 |
| 11 | `test_run_trigger` | run trigger returns a non-empty run_id and exits 0 |
| 12 | `test_run_status` | run status prints execution status |
| 13 | `test_run_cancel` | run cancel calls cancel endpoint and confirms cancellation |
| 14 | `test_schedule_list` | schedule list shows schedule entries |
| 15 | `test_schedule_create` | schedule create returns a schedule_id |
| 16 | `test_config_set_and_get_api_url` | config set api_url persists; config get api_url retrieves it |
| 17 | `test_api_url_flag_overrides_for_single_invocation` | --api-url flag is used for the invocation but not persisted |
