# Django API Test Backlog

This backlog maps every natural-language API scenario in `scenarios.md` to an
executable Django test task. Test function names use the scenario id with
hyphens converted to underscores, for example `API-TGT-001` becomes
`test_api_tgt_001_*`.

## Current Status

- Done: all listed scenarios below are covered by executable tests, including
  post-review contract-hardening regressions.
- Pending: none.

## Phase 1: Core API Contract

- [x] `API-COM-001` `test_api_com_001_request_id_is_returned_on_success`
- [x] `API-COM-002` `test_api_com_002_server_generates_request_id`
- [x] `API-COM-003` `test_api_com_003_validation_error_uses_standard_error_response`
- [x] `API-COM-004` `test_api_com_004_not_found_uses_standard_error_response`
- [x] `API-COM-005` `test_api_com_005_csv_query_array_is_accepted`
- [x] `API-COM-006` `test_api_com_006_repeated_query_array_is_rejected`
- [x] `API-COM-007` `test_api_com_007_internal_exception_uses_standard_error_response`
- [x] `API-LST-001` `test_api_lst_001_empty_list_endpoints_return_page_envelopes`
- [x] `API-HEALTH-001` `test_api_health_001_returns_dependency_status`
- [x] `API-HEALTH-002` `test_api_health_002_degrades_when_noncritical_dependency_is_down`
- [x] `API-META-001` `test_api_meta_001_static_reference_endpoints_are_cacheable`

## Phase 2: Targets

- [x] `API-TGT-001` `test_api_tgt_001_list_targets_filters_by_host`
- [x] `API-TGT-002` `test_api_tgt_002_create_target_returns_schema_with_default_context`
- [x] `API-TGT-003` `test_api_tgt_003_get_target_detail`
- [x] `API-TGT-004` `test_api_tgt_004_duplicate_target_returns_conflict`
- [x] `API-TGT-005` `test_api_tgt_005_context_patch_returns_recompute_job_id`
- [x] `API-TGT-006` `test_api_tgt_006_context_patch_enqueue_failure_rolls_back`
- [x] `API-TGT-007` `test_api_tgt_007_noop_patch_does_not_create_recompute_job`
- [x] `API-TGT-008` `test_api_tgt_008_delete_target_soft_unlinks_assets`
- [x] `API-TGT-009` `test_api_tgt_009_rejects_contract_invalid_target_fields`

## Phase 3: Jobs And Async Lifecycle

- [x] `API-JOB-001` `test_api_job_001_create_scan_job_returns_job_envelope`
- [x] `API-JOB-002` `test_api_job_002_scan_enqueue_failure_returns_503`
- [x] `API-JOB-002B` `test_api_job_002b_scan_create_rejects_unknown_scanner`
- [x] `API-JOB-002C` `test_api_job_002c_list_jobs_filters_kind_and_validates_status`
- [x] `API-JOB-003` `test_api_job_003_list_jobs_returns_page`
- [x] `API-JOB-004` `test_api_job_004_polling_returns_no_store_and_job_envelope`
- [x] `API-JOB-005` `test_api_job_005_completed_scan_job_returns_snapshot_result`
- [x] `API-JOB-006` `test_api_job_006_failed_job_returns_error_and_finished_at`
- [x] `API-JOB-007` `test_api_job_007_running_scan_and_discovery_cancel_sets_requested_at`
- [x] `API-JOB-008` `test_api_job_008_pending_recompute_can_be_cancelled`
- [x] `API-JOB-009` `test_api_job_009_running_recompute_cannot_be_cancelled`
- [x] `API-JOB-010` `test_api_job_010_terminal_job_cancel_returns_job_not_cancellable`
- [x] `API-JOB-011` `test_api_job_011_cancel_missing_job_returns_not_found`
- [x] `API-JOB-012` `test_api_job_012_job_logs_return_page`
- [x] `API-JOB-013` `test_api_job_013_agent_skip_log_is_visible`

## Phase 4: Discovery

- [x] `API-DSC-001` `test_api_dsc_001_list_discoveries_returns_page`
- [x] `API-DSC-002` `test_api_dsc_002_create_discovery_returns_job_envelope`
- [x] `API-DSC-002B` `test_api_dsc_002b_create_discovery_defaults_default_ports_to_true`
- [x] `API-DSC-002C` `test_api_dsc_002c_create_discovery_rejects_invalid_ports_and_status_filter`
- [x] `API-DSC-003` `test_api_dsc_003_detail_separates_created_and_started_at`
- [x] `API-DSC-004` `test_api_dsc_004_endpoint_list_separates_detected_and_suggested_protocol`
- [x] `API-DSC-005` `test_api_dsc_005_promote_endpoints_creates_targets`
- [x] `API-DSC-008` `test_api_dsc_008_promote_applies_per_promotion_target_fields`
- [x] `API-DSC-009` `test_api_dsc_009_promote_skips_already_promoted_and_missing_endpoints`
- [x] `API-DSC-010` `test_api_dsc_010_promote_rejects_invalid_protocol_and_context`
- [x] `API-DSC-006` `test_api_dsc_006_enqueue_failure_returns_503_without_orphans`
- [x] `API-DSC-007` `test_api_dsc_007_cancelled_discovery_preserves_partial_endpoints`

## Phase 5: Snapshots And Assets

- [x] `API-SNP-001` `test_api_snp_001_list_snapshots_returns_latest_first_page`
- [x] `API-SNP-002` `test_api_snp_002_get_snapshot_detail`
- [x] `API-SNP-003` `test_api_snp_003_export_snapshot_returns_cbom_download`
- [x] `API-SNP-004` `test_api_snp_004_diff_snapshots_returns_summary`
- [x] `API-AST-001` `test_api_ast_001_list_assets_with_filters_and_risk`
- [x] `API-AST-002` `test_api_ast_002_get_asset_detail_with_context_sources`
- [x] `API-AST-003` `test_api_ast_003_context_patch_distinguishes_omit_and_null`
- [x] `API-AST-004` `test_api_ast_004_context_patch_enqueue_failure_rolls_back`
- [x] `API-AST-005` `test_api_ast_005_qualitative_request_updates_existing_record`

## Phase 6: Risk

- [x] `API-RSK-001` `test_api_rsk_001_get_default_risk_weights`
- [x] `API-RSK-002` `test_api_rsk_002_list_snapshot_risks_with_filters`
- [x] `API-RSK-002B` `test_api_rsk_002b_empty_tier_filter_returns_empty_page`
- [x] `API-RSK-002C` `test_api_rsk_002c_list_snapshot_risks_applies_max_score_sort_and_missing_snapshot`
- [x] `API-RSK-002D` `test_api_rsk_002d_list_snapshot_risks_validates_min_score_and_sort`
- [x] `API-RSK-003` `test_api_rsk_003_put_weights_does_not_accept_updated_at`
- [x] `API-RSK-004` `test_api_rsk_004_put_weights_rejects_updated_at`
- [x] `API-RSK-005` `test_api_rsk_005_put_weights_rejects_out_of_range_values`
- [x] `API-RSK-006` `test_api_rsk_006_recompute_returns_recompute_job_envelope`
- [x] `API-RSK-007` `test_api_rsk_007_completed_recompute_returns_updated_scores_count`
- [x] `API-RSK-008` `test_api_rsk_008_recompute_enqueue_failure_returns_503`
- [x] `API-RSK-009` `test_api_rsk_009_top_risks_returns_limited_page`
- [x] `API-RSK-009B` `test_api_rsk_009b_top_risks_returns_404_for_missing_snapshot`
- [x] `API-RSK-010` `test_api_rsk_010_recompute_requires_weights`
- [x] `API-RSK-011` `test_api_rsk_011_recompute_rejects_incomplete_or_out_of_range_weights`

## Phase 7: Migration

- [x] `API-MIG-001` `test_api_mig_001_migration_plan_returns_recommendation_page`
- [x] `API-MIG-002` `test_api_mig_002_migration_impact_calculates_selected_assets_only`
- [x] `API-MIG-003` `test_api_mig_003_migration_impact_rejects_invalid_asset_ids`

## Phase 8: Agents

- [x] `API-AGT-001` `test_api_agt_001_register_agent_returns_token_once`
- [x] `API-AGT-002` `test_api_agt_002_existing_hostname_registration_rotates_token`
- [x] `API-AGT-003` `test_api_agt_003_missing_or_invalid_bootstrap_token_is_rejected`
- [x] `API-AGT-004` `test_api_agt_004_heartbeat_updates_last_seen`
- [x] `API-AGT-005` `test_api_agt_005_inactive_agent_heartbeat_is_rejected`
- [x] `API-AGT-006` `test_api_agt_006_list_agents_marks_stale_and_hides_tokens`
- [x] `API-AGT-007` `test_api_agt_007_agent_detail_hides_tokens`
- [x] `API-AGT-008` `test_api_agt_008_delete_agent_soft_deactivates`
- [x] `API-AGT-009` `test_api_agt_009_worker_skips_stale_or_capability_mismatch_agent`

## Phase 9: Dashboard

- [x] `API-DSH-001` `test_api_dsh_001_dashboard_summary_uses_latest_snapshot`
- [x] `API-DSH-002` `test_api_dsh_002_dashboard_empty_state_without_snapshots`
- [x] `API-DSH-003` `test_api_dsh_003_dashboard_does_not_expose_agent_tokens`
