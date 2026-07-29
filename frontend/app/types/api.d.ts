/**
 * api.d.ts — أنواع مُولَّدة من عقود OpenAPI المُلتزَمة (D-185).
 *
 * ⚠️ مُولَّد آلياً — لا تُحرّره يدوياً.
 * المصدر: docs/contracts/openapi/*.json
 * التوليد: python scripts/contracts/generate_frontend_types.py
 *
 * لماذا: المستودع «API-first» لكن الواجهة كانت تقرأ كل حقل نصّياً بلا أي ربط
 * بالعقود — فأي تغيير في عقد خدمة لم يكن يُكتشَف إلا في المتصفح. هذه الأنواع
 * تجعل انحراف العقد خطأ ترجمة في CI (`npm run typecheck`).
 */

// ── api_gateway (CogniForge API Gateway) ─────────
export interface ApiGatewayValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── auditor_service (Auditor Microservice) ─────────
export interface AuditorServiceConsultRequest { situation: string; analysis: Record<string, unknown> }
export interface AuditorServiceConsultResponse { recommendation: string; confidence: number }
export interface AuditorServiceReviewRequest { result: Record<string, unknown>; original_objective: string; context?: Record<string, unknown> }
export interface AuditorServiceReviewResponse { approved: boolean; feedback: string; score: number; final_response: string }
export interface AuditorServiceValidationError { loc: string | number[]; msg: string; type: string }

// ── content_retrieval_skill (content-retrieval-skill) ─────────
export interface ContentRetrievalSkillContentItemResponse { id: string; title: string; subject: string; year: string; tags: string[]; content_preview: string; file_path: string }
export interface ContentRetrievalSkillDeepDiveResponse { formula: string; explanation: string; why_zero: string }
export interface ContentRetrievalSkillHealthResponse { status: string; service: string; step: string; kb_path: string; kb_files: number; version: string }
export interface ContentRetrievalSkillImpossibleCaseRequest { bag_count: number; requested: number; item_name?: string }
export interface ContentRetrievalSkillImpossibleCaseResponse { is_impossible: boolean; case_type: string; stage_1?: Stage1SceneResponse | null; stage_2?: Stage2QuestionResponse | null; stage_3?: Stage3AnimationResponse | null; stage_4?: Stage4MessageResponse | null; deep_dive?: DeepDiveResponse | null }
export interface ContentRetrievalSkillRetrieveRequest { question: string; subject?: string | null; year?: string | null; max_results?: number }
export interface ContentRetrievalSkillRetrieveResponse { intent: string; intent_confidence: number; intent_reason: string; items: ContentItemResponse[]; total: number; duration_ms: number; kb_path: string; query_subject: string | null; query_year: string | null }
export interface ContentRetrievalSkillStage1SceneResponse { bag_count: number; requested: number; bag_label: string; request_label: string }
export interface ContentRetrievalSkillStage2QuestionResponse { question: string }
export interface ContentRetrievalSkillStage3AnimationResponse { animation: string; duration_ms: number }
export interface ContentRetrievalSkillStage4MessageResponse { message: string; tone: string }
export interface ContentRetrievalSkillValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── conversation_service (CogniForge Conversation Service) ─────────
export interface ConversationServiceChatRequest { question: string; thread_id?: string | null; history?: Record<string, unknown>[]; correlation_id?: string | null }
export interface ConversationServiceChatResponse { response: string; intent: string; subject?: string; thread_id: string; correlation_id: string; graph_ready: boolean; step?: string; ui_component?: Record<string, unknown> | null }
export interface ConversationServiceHealthResponse { status: string; service: string; version: string; step: string; graph_ready: boolean; ws_enabled: boolean }
export interface ConversationServiceValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── foundations_service (foundations-service) ─────────
export interface FoundationsServiceComputeRequest { domain: string; operation: string; args?: Record<string, unknown> }
export interface FoundationsServiceComputeResponse { domain: string; operation: string; ok: boolean; result?: unknown; error?: string | null; duration_ms: number }
export interface FoundationsServiceHealthResponse { status: string; service: string; step: string; version: string; domains: string[]; llm_backend: string }
export interface FoundationsServiceValidationError { loc: string | number[]; msg: string; type: string }

// ── memory_agent (Memory Agent) ─────────
export interface MemoryAgentConcept { concept_id: string; name_ar: string; name_en?: string; description?: string; subject?: string; level?: string; difficulty?: number; tags?: string[] }
export interface MemoryAgentHealthResponse { service: string; status: string; database?: string | null }
export interface MemoryAgentMemoryCreateRequest { content: string; tags?: string[] }
export interface MemoryAgentMemoryResponse { entry_id: string; content: string; tags: string[] }
export interface MemoryAgentMemorySearchFilters { tags?: string[] }
export interface MemoryAgentMemorySearchRequest { query?: string; filters?: MemorySearchFilters; limit?: number }
export interface MemoryAgentPathRequest { from_concept: string; to_concept: string }
export interface MemoryAgentReadinessRequest { concept_id: string; mastery_levels: Record<string, unknown> }
export interface MemoryAgentReadinessResponse { concept_id: string; concept_name: string; is_ready: boolean; readiness_score: number; missing_prerequisites: string[]; weak_prerequisites: string[]; recommendation: string }
export interface MemoryAgentValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── notation_service (notation-service) ─────────
export interface NotationServiceDefineRequest { symbol: string }
export interface NotationServiceDefineResponse { found: boolean; symbol?: SymbolPayload | null; error?: Record<string, unknown> | null; registry_version: string; duration_ms: number; trace_id: string }
export interface NotationServiceHealthResponse { status: string; service: string; step: string; version: string; registry_version: string; symbols_loaded: number; startup_state: string; llm_backend: string }
export interface NotationServiceResolveRequest { text: string }
export interface NotationServiceResolveResponse { found: boolean; symbol?: SymbolPayload | null; registry_version: string; duration_ms: number; trace_id: string }
export interface NotationServiceSymbolPayload { symbol: string; title: string; definition: string; example: string; concept_id?: string | null; property_id?: string | null }
export interface NotationServiceSymbolsResponse { symbols: SymbolPayload[]; count: number; registry_version: string }
export interface NotationServiceValidationError { loc: string | number[]; msg: string; type: string }

// ── observability_service (Observability Service) ─────────
export interface ObservabilityServiceAlertItem { id: string; severity: string; message: string; timestamp: string; status: string; service_name: string; metrics: Record<string, unknown> }
export interface ObservabilityServiceAlertsResponse { alerts: AlertItem[] }
export interface ObservabilityServiceCalculateMetricsRequest { findings: SecurityFindingSchema[]; code_metrics?: Record<string, unknown> | null }
export interface ObservabilityServiceCalculateRiskRequest { findings: SecurityFindingSchema[]; code_metrics?: Record<string, unknown> | null }
export interface ObservabilityServiceCalculateRiskResponse { risk_score: number }
export interface ObservabilityServiceCapacityPlanPayload { plan_id: string; service_name: string; current_capacity: number; recommended_capacity: number; forecast_horizon_hours: number; expected_peak_load: number; confidence: number; created_at: string }
export interface ObservabilityServiceCapacityPlanRequest { service_name: string; forecast_horizon_hours?: number }
export interface ObservabilityServiceCapacityPlanResponse { plan: CapacityPlanPayload }
export interface ObservabilityServiceEndpointAnalyticsResponse { path: string; avg_latency: number; p95_latency: number; error_count?: number; total_calls?: number }
export interface ObservabilityServiceErrorMetrics { error_rate: number; error_count: number }
export interface ObservabilityServiceForecastRequest { service_name: string; metric_type: MetricType; hours_ahead?: number }
export interface ObservabilityServiceForecastResponse { forecast_id: string; predicted_load: number; confidence_interval: unknown[] }
export interface ObservabilityServiceGoldenSignalsResponse { latency: LatencyMetrics; traffic: TrafficMetrics; errors: ErrorMetrics; saturation: SaturationMetrics }
export interface ObservabilityServiceHealthResponse { service: string; status: string; database?: string | null }
export interface ObservabilityServiceLatencyMetrics { p50: number; p95: number; p99: number; "p99.9": number; avg: number }
export type ObservabilityServiceMetricType = string;
export interface ObservabilityServiceMetricsResponse { metrics: Record<string, unknown> }
export interface ObservabilityServicePerformanceSnapshotResponse { cpu_usage: number; memory_usage: number; active_requests: number }
export interface ObservabilityServiceRiskPredictionRequest { historical_metrics: SecurityMetricsResponse[]; days_ahead?: number }
export interface ObservabilityServiceRiskPredictionResponse { predicted_risk: number; confidence: number; trend: string; slope: number; current_risk: number }
export interface ObservabilityServiceRootResponse { message: string }
export interface ObservabilityServiceSaturationMetrics { active_requests: number; queue_depth: number; active_spans?: number | null; resource_utilization?: number | null }
export interface ObservabilityServiceSecurityFindingSchema { id: string; severity: Severity; rule_id: string; file_path: string; line_number: number; message: string; cwe_id?: string | null; owasp_category?: string | null; first_seen?: string | null; last_seen?: string | null; false_positive?: boolean; fixed?: boolean; fix_time_hours?: number | null; developer_id?: string | null }
export interface ObservabilityServiceSecurityMetricsResponse { total_findings: number; critical_count: number; high_count: number; medium_count: number; low_count: number; findings_per_1000_loc: number; new_findings_last_24h: number; fixed_findings_last_24h: number; false_positive_rate: number; mean_time_to_detect: number; mean_time_to_fix: number; overall_risk_score: number; security_debt_score: number; trend_direction: string; findings_per_developer: Record<string, unknown>; fix_rate_per_developer: Record<string, unknown>; timestamp: string }
export type ObservabilityServiceSeverity = string;
export interface ObservabilityServiceTelemetryRequest { metric_id: string; service_name: string; metric_type: MetricType; value: number; timestamp?: string; labels?: Record<string, unknown>; unit?: string }
export interface ObservabilityServiceTelemetryResponse { status: string; metric_id: string }
export interface ObservabilityServiceTrafficMetrics { requests_per_second: number; total_requests: number }
export interface ObservabilityServiceValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── orchestrator_service (Orchestrator Service) ─────────
export interface OrchestratorServiceChatRequest { question: string; user_id: number; conversation_id?: number | null; history_messages?: Record<string, unknown>[]; context?: Record<string, unknown> }
export interface OrchestratorServiceComposeRequest { query: string; correlation_id?: string | null }
export interface OrchestratorServiceComposeResponse { correlation_id: string; query: string; composed_answer: string; pipeline_mode: string; skills_active: string[]; total_duration_ms: number; composition_confidence?: number; plan: SkillResultSchema; research: SkillResultSchema; reasoning: SkillResultSchema }
export type OrchestratorServiceJsonObject = Record<string, unknown>;
export interface OrchestratorServiceMissionCreate { objective: string; context?: Record<string, unknown>; priority?: number }
export interface OrchestratorServiceMissionEventResponse { event_type: string; mission_id: number; timestamp?: string; payload?: Record<string, unknown> }
export interface OrchestratorServiceMissionResponse { id: number; objective: string; status: MissionStatusEnum; outcome?: string | null; created_at: string; updated_at: string; result?: Record<string, unknown> | null; steps?: MissionStepResponse[] }
export type OrchestratorServiceMissionStatusEnum = string;
export interface OrchestratorServiceMissionStepResponse { id?: number | null; name: string; description?: string | null; status?: StepStatusEnum; result?: string | null; tool_used?: string | null; created_at: string; completed_at?: string | null }
export interface OrchestratorServiceOutboxRelayResponse { processed: number; published: number; failed: number; skipped: number }
export interface OrchestratorServiceOutboxStatusResponse { pending: number; processing: number; failed: number; published: number; oldest_pending_age_seconds: number | null; generated_at: string }
export interface OrchestratorServiceSkillResultSchema { skill: string; status: string; data: Record<string, unknown>; duration_ms: number; error?: string | null }
export type OrchestratorServiceStepStatusEnum = string;
export interface OrchestratorServiceValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── planning_agent (Planning Agent) ─────────
export interface PlanningAgentHealthResponse { service: string; status: string; database?: string | null }
export interface PlanningAgentPlanRequest { objective: string; context?: Record<string, unknown> | unknown[] }
export interface PlanningAgentPlanResponse { plan_id: string; goal: string; strategy_name: string; reasoning: string; steps: PlanStep[] }
export interface PlanningAgentPlanStep { name: string; description: string; tool_hint?: string | null }
export interface PlanningAgentValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── reasoning_agent (Reasoning Agent) ─────────
export interface ReasoningAgentAgentRequest { caller_id: string; target_service?: string; action: string; payload?: Record<string, unknown>; security_token?: string | null }
export interface ReasoningAgentAgentResponse { status: string; data?: unknown | null; error?: string | null; metrics?: Record<string, unknown> }
export interface ReasoningAgentValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── research_agent (Research Agent) ─────────
export interface ResearchAgentAgentRequest { caller_id: string; target_service?: string; action: string; payload?: Record<string, unknown>; security_token?: string | null }
export interface ResearchAgentAgentResponse { status: string; data?: unknown | null; error?: string | null; metrics?: Record<string, unknown> }
export interface ResearchAgentValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── user_service (user-service) ─────────
export interface UserServiceAdminCreateUserRequest { full_name: string; email: string; password: string; is_admin?: boolean }
export interface UserServiceAuthResponse { access_token: string; token_type?: string; user: UserResponse; status?: string; landing_path?: string }
export interface UserServiceChangePasswordRequest { current_password: string; new_password: string }
export interface UserServiceHealthResponse { service: string; status: string; environment?: string | null }
export interface UserServiceLoginRequest { email: string; password: string }
export interface UserServiceLogoutRequest { refresh_token: string }
export interface UserServicePasswordResetConfirmRequest { token: string; new_password: string }
export interface UserServicePasswordResetRequest { email: string }
export interface UserServicePasswordResetResponse { status?: string; reset_token?: string | null; expires_in?: number | null }
export interface UserServiceProfileUpdateRequest { full_name?: string | null; email?: string | null }
export interface UserServiceReauthRequest { password: string }
export interface UserServiceReauthResponse { reauth_token: string; expires_in: number }
export interface UserServiceRefreshRequest { refresh_token: string }
export interface UserServiceRegisterRequest { full_name: string; email: string; password: string }
export interface UserServiceRegisterResponse { status?: string; message: string; user: UserResponse }
export interface UserServiceRoleAssignmentRequest { role_name: string; reauth_password?: string | null; reauth_token?: string | null; justification?: string | null }
export interface UserServiceStatusUpdateRequest { status: UserStatus }
export interface UserServiceTokenGenerateResponse { access_token: string; refresh_token: string; token_type?: string }
export interface UserServiceTokenVerifyRequest { token?: string | null }
export interface UserServiceTokenVerifyResponse { status: string; data: Record<string, unknown> }
export interface UserServiceUserOut { id: number; email: string; full_name: string; is_active: boolean; status: UserStatus; roles?: string[] }
export interface UserServiceUserResponse { id: number; name: string; full_name?: string | null; email: string; is_admin?: boolean }
export type UserServiceUserStatus = string;
export interface UserServiceValidationError { loc: string | number[]; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown> }

// ── WebSocket chat event contract (shared/chat_protocol) ─────────
export type ChatEventType =
    | 'conversation_init'
    | 'assistant_delta'
    | 'assistant_final'
    | 'persisted'
    | 'complete'
    | 'error';

export interface ChatEvent {
    type: ChatEventType;
    payload?: {
        content?: string;
        conversation_id?: number;
        request_id?: string;
        ui_component?: Record<string, unknown> | null;
        code?: string;
    };
    persisted?: boolean;
}
