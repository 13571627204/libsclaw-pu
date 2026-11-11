import { isAxiosError, type AxiosResponse } from "axios";
import { apiV1Client } from "./http";

export interface PharmaField {
  field_code: string;
  label: string;
  value: string;
  machine_value: string;
  normalized_value?: unknown;
  confidence: number;
  level: "high" | "medium" | "low" | "none";
  critical: boolean;
  dimension: string;
  document_id?: string | null;
  page_no: number | null;
  source_text: string;
  source_type:
    | "document_extracted"
    | "manual"
    | "manual_input"
    | "manual_review"
    | "manual_review_text";
  polygon?: number[][] | null;
  confirmed: boolean;
  modified_by_human?: boolean;
  conflict?: boolean;
  incomplete_source?: boolean;
}

export interface PharmaKeyword {
  keyword_id: string;
  keyword: string;
  source_type:
    | "document_extracted"
    | "platform_observed"
    | "enterprise_history"
    | "model_suggested"
    | "manual_input"
    | "manual_review"
    | "manual";
  source_field: string;
  source_label: string;
  source_text: string;
  platform?: string | null;
  observed_at?: string | null;
  page_no: number | null;
  confidence: number;
  priority_score: number;
  score_breakdown?: Record<string, number>;
  selected: boolean;
  status: "pending_confirmation" | "confirmed" | "rejected";
}

export interface PharmaDimensionItem {
  item_id?: string;
  text?: string;
  value?: string;
  source_field?: string;
  source_type?: string;
  source_label?: string;
  model_provider?: string;
  is_inferred?: boolean;
  is_external?: boolean;
  source_url?: string;
  derivation?: string;
  evidence_ids?: string[];
  evidence?: Array<{
    evidence_id: string;
    source_label: string;
    source_text: string;
    page_no: number | null;
  }>;
  source_text?: string;
  page_no?: number | null;
  claim_id?: string | null;
  confirmed?: boolean;
  status?: string;
}

export interface PharmaDimension {
  dimension_id?: string;
  dimension_code?: string;
  code?: string;
  label?: string;
  name?: string;
  items: PharmaDimensionItem[];
  confirmed?: boolean;
}

export interface PharmaSafetyConstraint {
  constraint_id?: string;
  field_code?: string;
  label: string;
  value?: string;
  text?: string;
  source_text?: string;
  page_no?: number | null;
  confirmed?: boolean;
}

export interface PharmaSceneLinkedClaim {
  claim_id: string;
  claim_no: string;
  text: string;
  claim_type: string;
  evidence_level: "strong" | "weak" | "none";
  marker: "🟢" | "🟡" | "🔴";
}

export interface PharmaUserVoice {
  voice_id: string;
  text: string;
  source: string;
  imported_by?: string;
  imported_at?: string;
}

export interface PharmaScene {
  scene_id: string;
  scene_no?: string;
  name: string;
  cluster?: string;
  cluster_label?: string;
  target_audience?: string;
  audience: string[] | string;
  audience_scope?: { claim_nos: string[]; texts: string[] };
  symptom_keywords?: string[];
  matched_terms?: string[];
  time_of_day?: string;
  location?: string;
  trigger_event?: string;
  trigger: string;
  core_pain?: string;
  search_keywords?: string[];
  keywords_notice?: string;
  inner_monologue?: string;
  content_hook?: string;
  trust_anchors?: string[];
  brand_product?: string[];
  existing_channels?: string[];
  linked_claims?: PharmaSceneLinkedClaim[];
  user_voices?: Array<Pick<PharmaUserVoice, "voice_id" | "text" | "source">>;
  user_voices_notice?: string;
  generation_mode?: string;
  user_language: string[];
  allowed_claim_ids: string[];
  blocked_topics: string[];
  recommended_platforms: string[];
  evidence_coverage: number;
  selected?: boolean;
  deleted?: boolean;
  priority?: "" | "strong" | "weak";
  note?: string;
  status: string;
}

export interface PharmaEvidence {
  document_id?: string;
  title?: string;
  version?: string;
  page_no?: number | null;
  source_text?: string;
  evidence_level?: "strong" | "weak" | "none";
}

export interface PharmaClaim {
  claim_id: string;
  text?: string;
  claim_text?: string;
  claim_type?: string;
  source_field?: string;
  source_text?: string;
  page_no?: number | null;
  evidence_level: "strong" | "weak" | "none";
  evidence?: PharmaEvidence[];
  medical_confirmed?: boolean;
  allowed?: boolean;
  status?: string;
}

export interface PharmaLiteratureCitation {
  citation_id: string;
  source_channel: "leaflet" | "uploaded" | "knowledge_base" | "pubmed";
  source_kind: string;
  source_kind_label?: string;
  source_label: string;
  excerpt: string;
  page_no?: number | null;
  url?: string;
  matched_terms?: string[];
  score: number;
}

export interface PharmaTripleCard {
  usable_scenes: string[];
  blocked_scenes: string[];
  compliant_copy: string;
  violation_copy: string;
  disclaimer: string;
  citation_summary?: string;
  verdict_note?: string;
  expression_rule?: string;
  disposal?: string;
  copy_source?: "template" | "ai" | string;
}

export interface PharmaLiteratureClaim {
  claim_id: string;
  claim_no: string;
  claim_type: "ingredients" | "efficacy" | "audience" | "endorsement";
  claim_type_label?: string;
  text: string;
  source_field?: string;
  source_label?: string;
  source_text?: string;
  source_type?: string;
  page_no?: number | null;
  citations: PharmaLiteratureCitation[];
  matched_terms?: string[];
  evidence_level: "strong" | "weak" | "none";
  match_status?: "pending" | "matched";
  accepted: boolean;
  status?: string;
  adjust_reason?: string;
  adjusted_by_human?: boolean;
  verdict_note?: string;
  expression_rule?: string;
  disposal?: string;
  ai_analysis?: {
    model_provider?: string;
    suggested_level?: "strong" | "weak" | "none";
    reason?: string;
    citation_ids?: string[];
    verdict_note?: string;
    expression_rule?: string;
    disposal?: string;
  } | null;
  ai_adjusted?: boolean;
  prior_review?: {
    claim_no?: string;
    accepted?: boolean;
    evidence_level?: string;
    adjust_reason?: string;
  } | null;
  triple_card: PharmaTripleCard;
}

export type LiteratureTier = "light" | "standard" | "deep";

export interface PharmaKnowledgeTriple {
  claim_no: string;
  ingredient: string;
  target: string;
  indication: string;
  basis_citation_ids: string[];
  hint_only?: boolean;
}

export interface PharmaTripleTableRow {
  claim_no: string;
  claim_type?: string;
  claim_type_label?: string;
  text: string;
  evidence_level: string;
  evidence_label?: string;
  verdict_note?: string;
  expression_rule?: string;
  disposal?: string;
  citation_summary?: string;
  citation_urls?: string[];
  usable_scenes?: string[];
  blocked_scenes?: string[];
  compliant_copy?: string;
  violation_copy?: string;
  adjust_reason?: string;
  status?: string;
}

export interface PharmaLiteratureSignoff {
  signer_name: string;
  signer_title: string;
  signer_qualified?: boolean;
  checklist?: Record<string, boolean>;
  operator?: string;
  signed_at?: string;
  workflow_version?: number;
  accepted_count?: number;
  blocked_count?: number;
  triple_table?: PharmaTripleTableRow[];
}

export interface PharmaLiteratureRedline {
  sku_key?: string;
  product_name?: string;
  project_id?: string;
  claim_no?: string;
  claim_type?: string;
  text: string;
  evidence_level?: string;
  verdict?: string;
  reason?: string;
  disposal?: string;
  violation_copy?: string;
  signer?: string;
  archived_at?: string;
}

export interface PharmaContentFootnote {
  index: number;
  claim_id?: string;
  claim_no?: string;
  source_label: string;
  page_no?: number | null;
  url?: string;
  text: string;
}

export interface PharmaLiteratureDocument {
  doc_id: string;
  filename: string;
  doc_kind: string;
  doc_kind_label?: string;
  uploaded_by?: string;
  uploaded_at?: string;
  char_count?: number;
  chunk_count?: number;
}

export interface PharmaLiteratureState {
  documents: PharmaLiteratureDocument[];
  kb_ids: string[];
  kb_names: string[];
  matched_at?: string | null;
  ai_notice?: string;
  tier?: LiteratureTier;
  tier_notice?: string;
  knowledge_graph?: PharmaKnowledgeTriple[];
  reused_from?: {
    project_id?: string;
    signed_at?: string;
    signer?: string;
    review_count?: number;
  } | null;
}

export interface PharmaUnusableClaim {
  claim_id: string;
  claim_no?: string;
  claim_type?: string;
  text: string;
  evidence_level?: string;
  reason?: string;
  disposal?: string;
  archived_at?: string;
}

export interface ComplianceRisk {
  risk_id?: string;
  rule_id?: string;
  rule_version?: number | string;
  kb_version?: string;
  level:
    | "block"
    | "caution"
    | "replace"
    | "pass"
    | "违规/阻断"
    | "谨慎"
    | "合规";
  content_id?: string;
  platform?: string;
  message: string;
  matched_text?: string;
  legal_basis?: string;
  suggestion?: string;
  replacement?: string;
  source?: "rule" | "ai" | string;
  position?: number | null;
  category?: string;
  sample_source?: string;
  filter_rule_version?: string;
  delete_only?: boolean;
}

export type ComplianceLabel = "pass" | "caution" | "blocked";

export interface ComplianceReviewDecision {
  decision: "adopt" | "keep";
  note?: string;
}

export interface ComplianceAiReview {
  provider_label?: string;
  notice?: string;
  kb_ids?: string[];
  kb_names?: string[];
  kb_warning?: string;
  kb_hits?: Array<{
    kb_name?: string;
    doc_name?: string;
    score?: number;
    excerpt?: string;
  }>;
  finding_count?: number;
  retrieved_at?: string;
}

export interface ComplianceCrossValidationItem {
  risk_id?: string;
  content_id?: string;
  rule_id?: string;
  level?: string;
  matched_text?: string;
  zr_basis?: string;
  verdict: "consistent" | "rule_only" | "ai_only" | string;
  search_refs?: string[];
  note?: string;
}

export interface ComplianceCrossValidation {
  baseline?: string;
  engine?: string;
  engine_type?: string;
  notice?: string;
  warning?: string;
  queries?: string[];
  sources?: Array<{ ref: string; title?: string; url?: string; snippet?: string; query?: string }>;
  items?: ComplianceCrossValidationItem[];
  summary?: { consistent?: number; rule_only?: number; ai_only?: number };
  conclusion?: string;
  validated_at?: string;
}

export interface ComplianceExpertTicket {
  ticket_id: string;
  question: string;
  risk_ids: string[];
  status: "open" | "answered" | string;
  scope?: "compliance" | "compliance_filter" | string;
  expert_team?: string;
  kb_version?: string;
  created_by?: string;
  created_at?: string;
  due_at?: string;
  answer?: string;
  answered_by?: string;
  answered_at?: string;
}

export interface ComplianceAiAnswer {
  answer: string;
  provider?: string;
  kb_version?: string;
  answered_at?: string;
  notice?: string;
}

export interface ComplianceKnowledgeBase {
  builder: string;
  builder_profile?: string;
  endorsement?: string;
  kb_version: string;
  rule_version?: number | string;
  released_at?: string;
  layers: Array<{ layer_id: string; name: string; items: string[] }>;
  update_mechanism: string[];
  labels?: Record<string, unknown>;
  expert_sla_hours: number;
  redline_rules: Array<{
    rule_id: string;
    product_types: string[];
    message: string;
    legal_basis: string;
    suggestion: string;
  }>;
  caution_rules: Array<{ rule_id: string; message: string; legal_basis: string }>;
  replacements: Array<{ original: string; replacement: string }>;
  platforms: Record<string, string[]>;
  filter_rule_version?: string;
  filter_basis?: string;
  filter_categories?: Record<string, string>;
  filter_redline_rules?: Array<{
    rule_id: string;
    category?: string;
    category_text?: string;
    product_types?: string[];
    message: string;
    legal_basis: string;
    suggestion?: string;
  }>;
  filter_caution_rules?: Array<{
    rule_id: string;
    message: string;
    legal_basis: string;
    suggestion?: string;
  }>;
  /** replacement 为空串 = 删除，无替换 */
  filter_replacements?: Array<{ original: string; replacement: string }>;
  filter_notice?: string;
  disposal_actions?: Record<string, string>;
}

export interface FilterInventoryItem {
  inventory_id?: string;
  platform: string;
  channel: string;
  date: string;
  url: string;
  account: string;
  title: string;
  body: string;
  is_brand_matrix: boolean;
  is_koc: boolean;
  koc_verified: boolean;
  label?: string;
  label_text?: string;
  disposal_status?: string;
}

export interface FilterDisposal {
  disposal_id: string;
  inventory_id: string;
  title: string;
  location: string;
  url?: string;
  action: "takedown" | "stop_promotion" | "full_review" | "revise" | string;
  action_text: string;
  reason: string;
  risk_ids: string[];
  status: "pending" | "done" | "scheduled" | string;
  note: string;
  scheduled_date: string;
}

export interface FilterMandatoryRecord {
  inventory_id: string;
  title: string;
  checks: Array<{ code: string; label: string; passed: boolean }>;
  passed: boolean;
}

export interface FilterSample {
  content_id: string;
  source: "inventory" | "competitor" | string;
  platform: string;
  channel?: string;
  title: string;
  body?: string;
  url?: string;
  label: ComplianceLabel | string;
  label_text: string;
}

export interface ComplianceFilterRecord {
  record_id: string;
  kb_builder?: string;
  endorsement?: string;
  kb_version?: string;
  rule_version?: number | string;
  filter_rule_version?: string;
  retrieval_date?: string;
  scanned_at?: string;
  basis?: string;
  label?: string;
  summary?: Record<string, number>;
  risk_count?: number;
  caution_reviewed?: number;
  replace_adopted?: number;
  disposal_count?: number;
  ad_review_schedule?: { apply_date: string; authority?: string; note?: string };
  expert_ticket_ids?: string[];
  confirm_checks?: string[];
  signer_name?: string;
  signer_title?: string;
  operator?: string;
  comment?: string;
  signed_at?: string;
}

export interface ComplianceFilterState {
  status: string;
  label: ComplianceLabel | "" | string;
  label_text: string;
  rule_version?: number | string;
  kb_version?: string;
  filter_rule_version?: string;
  product_type?: string;
  basis?: string;
  samples: FilterSample[];
  inventory: FilterInventoryItem[];
  risks: ComplianceRisk[];
  summary: { pass?: number; caution?: number; blocked?: number };
  category_summary: Record<
    string,
    { label: string; block: number; caution: number; replace: number }
  >;
  disposals: FilterDisposal[];
  mandatory_elements: FilterMandatoryRecord[];
  inventory_digest?: string;
  kb_hits: Array<{ kb_name?: string; doc_name?: string; score?: number; excerpt?: string }>;
  ai_review: ComplianceAiReview | null;
  cross_validation: ComplianceCrossValidation | null;
  rx_patient_only?: boolean;
  reviews?: Record<string, ComplianceReviewDecision & { level?: string; rule_id?: string }>;
  scanned_at: string | null;
  record: ComplianceFilterRecord | null;
  confirmed_at: string | null;
  confirmed_by: string | null;
  legacy_skipped?: boolean;
}

export interface ComplianceRecord {
  record_id: string;
  kb_builder?: string;
  endorsement?: string;
  kb_version?: string;
  rule_version?: number | string;
  retrieval_date?: string;
  scanned_at?: string;
  label?: string;
  summary?: Record<string, number>;
  risk_count?: number;
  caution_reviewed?: number;
  replace_adopted?: number;
  citation_covered?: boolean;
  expert_ticket_ids?: string[];
  signer_name?: string;
  signer_title?: string;
  duration_minutes?: number;
}

export interface PharmaContent {
  content_id: string;
  platform: string;
  title?: string;
  body?: string;
  body_with_footnotes?: string;
  footnotes?: PharmaContentFootnote[];
  content?: string;
  claim_ids: string[];
  scene_id?: string | null;
  status: string;
  risks?: ComplianceRisk[];
  compliance_status?: string;
  compliance_label?: ComplianceLabel;
  compliance_label_text?: string;
  version?: number;
  channel?: string;
  content_type?: string;
  length_spec?: string;
  scene_no?: string;
  batch_role?: "sample" | "full" | "comment_replies";
  title_options?: string[];
  hashtags?: string[];
  publish_time?: { slot?: string; reason?: string };
  assets?: string[];
  faq?: Array<{ q: string; a: string }>;
  ad_review_tips?: string[];
  segments?: Array<{ label: string; text: string; note: string }>;
  quality_issues?: string[];
  unverified_claim_refs?: string[];
  claim_nos?: string[];
  sample_no?: number;
  images?: Array<{
    index: number;
    asset: string;
    prompt: string;
    filename: string;
    model: string;
    size: string;
    aspect?: string;
    created_at: string;
  }>;
  image_errors?: string[];
  publish_status?: PublishStatus;
  publish_url?: string;
  published_at?: string;
  is_hit?: boolean;
}

export type PublishStatus =
  | "unscheduled"
  | "scheduled"
  | "published"
  | "paused"
  | "offline";

export interface AuditChainRow {
  step: number;
  step_label: string;
  name: string;
  confirmer: string;
  trace: string;
  status: string;
  status_text: string;
  output: string;
  confirmed_at?: string | null;
  signer?: string;
  comment?: string;
}

export interface FinalApprovalPayload {
  signer_name: string;
  signer_title: string;
  checklist: string[];
  duration_minutes: number;
  business_goal_note?: string;
  publish_authorization: {
    authorized: boolean;
    channels?: string[];
    start_date?: string;
    note?: string;
  };
}

export interface PerformanceRecord {
  content_id: string;
  channel?: string;
  title?: string;
  platform: string;
  platform_text?: string;
  impressions: number;
  likes: number;
  collects: number;
  comments: number;
  shares: number;
  engagements: number;
  engagement_rate: number;
  is_hit: boolean;
  captured_at?: string;
}

export interface FinalReview {
  review_id: string;
  reason: string;
  reason_text: string;
  comment: string;
  operator: string;
  time: string;
  target_step: number;
  was_approved: boolean;
}

export interface SkuReuseStatus {
  available: boolean;
  source_project_id?: string;
  archived_at?: string;
  reusable_steps?: number[];
  rule_changed?: boolean;
}

export type PharmaApprovalExportKind =
  | "approval-report.md"
  | "approval.xlsx"
  | "feishu-bitable.xlsx"
  | "full-report.json";

export interface ContentBatchTopic {
  no: number;
  title: string;
  channel: string;
  claim_nos: string[];
  publish_time: string;
  redline: string;
  selected: boolean;
}

export interface ContentBatch {
  topic_matrix: Array<{
    group: string;
    scene_no: string;
    group_name: string;
    topics: ContentBatchTopic[];
  }>;
  topic_count: number;
  selected_topic_count?: number;
  topics_scheduled_at?: string;
  platform_plan: Array<{
    platform: string;
    form: string;
    monthly_count: string;
    note: string;
  }>;
  comment_replies: Array<{ q: string; a: string }>;
  channels: string[];
  total: number;
  scene_count: number;
  gap_count: number;
  generated_at: string;
  provider_label: string;
  failed_groups: string[];
  content_count?: number;
  channel_stats?: Array<{ channel: string; quota: number; generated: number }>;
  reworks?: Array<{
    channel: string;
    reason: string;
    reason_text: string;
    comment: string;
    operator: string;
    time: string;
    replaced: number;
    generated: number;
    provider_label: string;
  }>;
}

export interface PharmaWorkflow {
  current_step: number;
  status: string;
  state?: string;
  version?: number;
  step_status?: Record<string, string>;
  terminated_reason?: string | null;
}

export interface PharmaApprovals {
  market?: Record<string, unknown> | null;
  medical?: Record<string, unknown> | null;
  compliance?: (Record<string, unknown> & { record?: ComplianceRecord }) | null;
  final?: Record<string, unknown> | null;
}

export interface PharmaUserNote {
  note_id: string;
  title?: string;
  text: string;
  created_at?: string;
  created_by?: string;
}

export type CompetitorPlatform = "douyin" | "xiaohongshu" | "zhihu" | "ecommerce";
export type CompetitorMode = "light" | "standard" | "deep";

export interface CompetitorItem {
  item_id: string;
  platform: CompetitorPlatform;
  kind: "post" | "comment" | "hot" | "product" | "page";
  channel?: string;
  keyword?: string;
  title?: string;
  text?: string;
  author?: string;
  likes?: number | null;
  comments?: number | null;
  shares?: number | null;
  collects?: number | null;
  heat?: number | null;
  price?: number | null;
  url?: string;
  source_mode?: CompetitorMode;
  collected_at?: string;
}

export interface CompetitorGap {
  gap_id: string;
  scene: string;
  our_scene_no?: string;
  competitor_coverage: number;
  evidence?: string;
  evidence_engagement?: number;
  opportunity: string;
  action?: string;
  entry_angle?: string;
  suggested_priority: "P0" | "P1";
  priority: "" | "P0" | "P1";
  selected: boolean;
  item_ids: string[];
}

export interface CompetitorAnalysis {
  formula_templates: Array<{
    template_id: string;
    platform?: string;
    opening?: string;
    middle?: string;
    ending?: string;
    item_ids: string[];
  }>;
  trust_anchors: Array<{
    type: string;
    label: string;
    usage_count: number;
    usage_status?: string;
    stance?: "" | "follow" | "avoid" | "lead" | "leverage" | "reverse";
    item_ids: string[];
    suggestion?: string;
  }>;
  gap_map: CompetitorGap[];
  user_voices: Array<{
    item_id: string;
    platform: string;
    channel?: string;
    likes?: number | null;
    pain_point?: string;
    quote: string;
    url?: string;
  }>;
  platform_strategy: Array<{
    platform: string;
    platform_label: string;
    tone?: string;
    strategy: string;
    item_ids: string[];
  }>;
  content_heatmap?: Array<{
    theme: string;
    signal: "hot" | "new" | "warning" | "stable";
    engagement: number;
    item_ids: string[];
    commercial_item_ids?: string[];
    note?: string;
  }>;
  price_tiers?: Array<{
    tier: string;
    tier_label?: string;
    brand: string;
    spec?: string;
    price?: string;
    daily_cost?: string;
    positioning?: string;
    item_ids: string[];
  }>;
  our_position?: { price: string; spec: string; daily_cost: string; note: string };
  competitor_signals?: Array<{
    signal_id: string;
    brand?: string;
    signal: string;
    item_ids: string[];
    suggested_response?: string;
  }>;
  radar_brands?: string[];
  sample_assessment?: {
    sufficient: boolean;
    post_count?: number;
    price_count?: number;
    platform_counts?: Partial<Record<CompetitorPlatform, number>>;
    missing?: string[];
    suggested_keywords?: string[];
    suggested_platforms?: CompetitorPlatform[];
    note: string;
  };
  compliance_note?: string;
}

export interface CompetitorState {
  mode: CompetitorMode | "";
  platforms: string[];
  keywords: string[];
  brands: string[];
  urls: string[];
  items: CompetitorItem[];
  warnings: string[];
  scans: Array<{
    scan_id: string;
    mode: CompetitorMode;
    mode_label: string;
    platforms: string[];
    keywords: string[];
    per_keyword?: number;
    keyword_counts?: Array<{ platform: string; keyword: string; count: number }>;
    url_count: number;
    fetched: number;
    added: number;
    warnings: string[];
    operator: string;
    time: string;
  }>;
  collected_at: string | null;
  analysis: CompetitorAnalysis;
  analyzed_at: string | null;
  provider_label: string;
  analysis_stale: boolean;
  our_price?: string;
  radar_brands?: string[];
  signal_responses?: Array<{ signal_id: string; response: string }>;
  confirmed_at: string | null;
  confirmed_by: string | null;
  legacy_skipped?: boolean;
}

export interface CompetitorCapabilities {
  platforms: Record<CompetitorPlatform, string>;
  modes: Record<CompetitorMode, string>;
  tikhub_configured: boolean;
  opencli_available: boolean;
}

export interface PharmaProjectSummary {
  project_id: string;
  product_name: string;
  product_type: string;
  status: string;
  workflow_step?: number;
  workflow_status?: string;
  filename: string;
  ocr_provider: string;
  field_count: number;
  keyword_count: number;
  created_at: string;
  updated_at: string;
}

export interface PharmaProject {
  project_id: string;
  product_name: string;
  product_type: string;
  status: string;
  filename: string;
  ocr_provider: string;
  created_at: string;
  updated_at: string;
  quality: {
    status: string;
    warnings: Array<{ code: string; message: string }>;
    metrics: Record<string, number>;
  };
  pages: Array<{
    page_no: number;
    text: string;
    confidence: number;
    blocks?: Array<Record<string, unknown>>;
  }>;
  fields: PharmaField[];
  keywords: PharmaKeyword[];
  workflow?: PharmaWorkflow;
  dimensions?: PharmaDimension[];
  dimension_generation?: {
    drug_name?: string;
    kb_ids?: string[];
    kb_hits?: number;
    search_hits?: number;
    search_mode?: string;
    dropped?: number;
    warnings?: string[];
    model_provider?: string;
    generated_at?: string;
  };
  safety_constraints?: PharmaSafetyConstraint[];
  scenes?: PharmaScene[];
  competitor?: CompetitorState;
  compliance_filter?: ComplianceFilterState;
  user_voices_pool?: PharmaUserVoice[];
  claims?: PharmaClaim[];
  literature?: PharmaLiteratureState;
  literature_claims?: PharmaLiteratureClaim[];
  unusable_claims?: PharmaUnusableClaim[];
  literature_signoff?: PharmaLiteratureSignoff | null;
  contents?: PharmaContent[];
  content_batch?: ContentBatch | null;
  compliance?: {
    status?: string;
    risks?: ComplianceRisk[];
    scanned_at?: string | null;
    label?: string;
    label_text?: string;
    rule_version?: number | string;
    kb_version?: string;
    kb_builder?: string;
    summary?: { pass?: number; caution?: number; blocked?: number };
    reviews?: Record<string, ComplianceReviewDecision>;
    ai_review?: ComplianceAiReview | null;
    cross_validation?: ComplianceCrossValidation | null;
    patient_management_only?: boolean;
  };
  compliance_tickets?: ComplianceExpertTicket[];
  approvals?: PharmaApprovals;
  audit_chain?: AuditChainRow[];
  final_reviews?: FinalReview[];
  performance?: { records: PerformanceRecord[]; updated_at?: string | null };
  version_history?: Array<Record<string, unknown>>;
  user_notes?: PharmaUserNote[];
  confirmed_at: string | null;
  confirmed_by: string | null;
  audit_events: Array<Record<string, unknown>>;
}

interface Envelope<T> {
  status: "ok" | "error";
  message?: string;
  data: T;
}

export type PharmaWorkflowAction =
  | "confirm_profile"
  | "confirm_dimensions"
  | "confirm_literature"
  | "confirm_scenes"
  | "confirm_competitor"
  | "confirm_compliance_filter"
  | "confirm_keywords"
  | "confirm_evidence"
  | "generate_contents"
  | "market_confirm"
  | "compliance_confirm"
  | "final_approve"
  | "rework"
  | "terminate";

const RECOVER_POLL_MS = 10000;

// 长耗时 AI 请求的连接被代理/浏览器中断（Network Error）时，后端仍在后台完成并落盘；
// 这里轮询项目，待 updated_at 变化后把最新项目当作本次请求结果返回。
async function withProjectRecovery(
  projectId: string,
  maxWaitMs: number,
  send: () => Promise<AxiosResponse<Envelope<PharmaProject>>>,
) {
  const fetchProject = () =>
    apiV1Client.get<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}`,
    );
  let before = "";
  const startedAt = Date.now();
  try {
    before = (await fetchProject()).data.data?.updated_at || "";
  } catch {
    // 取不到基线时改用请求发起时间判定项目是否已被本次请求更新
  }
  const isUpdated = (updatedAt: string) => {
    if (!updatedAt) return false;
    if (before) return updatedAt !== before;
    const ts = Date.parse(updatedAt);
    return !Number.isNaN(ts) && ts >= startedAt - 5000;
  };
  try {
    return await send();
  } catch (error) {
    if (!isAxiosError(error) || error.code !== "ERR_NETWORK") {
      throw error;
    }
    const deadline = Date.now() + maxWaitMs;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, RECOVER_POLL_MS));
      try {
        const response = await fetchProject();
        if (isUpdated(response.data.data?.updated_at || "")) return response;
      } catch {
        // 后端短暂不可达时继续等待
      }
    }
    throw error;
  }
}

// 后台内容任务：POST 立即返回，随后轮询状态（网络抖动继续轮询），不依赖长连接
async function runContentJob(
  projectId: string,
  kind: "rework" | "auto-fix",
  payload: object,
  maxWaitMs: number,
  label: string,
) {
  type Job = { status: string; error?: string };
  const url = `/pharma-translator/projects/${projectId}/content-batch/${kind}`;
  await apiV1Client.post<Envelope<Job>>(url, payload, { timeout: 30000 });
  const deadline = Date.now() + maxWaitMs;
  let finished = false;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    let job: Job | undefined;
    try {
      job = (await apiV1Client.get<Envelope<Job>>(url, { timeout: 15000 })).data.data;
    } catch (error) {
      if (isAxiosError(error) && !error.response) continue;
      if (isAxiosError(error) && error.response?.status === 503) continue;
      throw error;
    }
    if (job?.status === "failed") throw job.error || `${label}失败`;
    if (job?.status === "done") {
      finished = true;
      break;
    }
    if (job?.status === "idle") {
      throw `${label}任务已中断（后端服务可能已重启），未完成的修改不会保存，请重新${label}`;
    }
  }
  if (!finished) throw `${label}仍在后台处理，请稍后刷新查看结果`;
  return apiV1Client.get<Envelope<PharmaProject>>(
    `/pharma-translator/projects/${projectId}`,
  );
}

export const pharmaTranslatorApi = {
  async analyze(payload: {
    productName: string;
    productType: string;
    file: File;
    manualText?: string;
  }) {
    const form = new FormData();
    form.append("product_name", payload.productName);
    form.append("product_type", payload.productType);
    form.append("manual_text", payload.manualText || "");
    form.append("file", payload.file);
    return apiV1Client.post<Envelope<PharmaProject>>(
      "/pharma-translator/analyze",
      form,
      { timeout: 300000 },
    );
  },

  list() {
    return apiV1Client.get<Envelope<PharmaProjectSummary[]>>(
      "/pharma-translator/projects",
    );
  },

  get(projectId: string) {
    return apiV1Client.get<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}`,
    );
  },

  delete(projectId: string) {
    return apiV1Client.delete<Envelope<{ project_id: string }>>(
      `/pharma-translator/projects/${projectId}`,
    );
  },

  confirm(
    projectId: string,
    payload: {
      fields: PharmaField[];
      keywords: PharmaKeyword[];
      comment: string;
    },
  ) {
    return withProjectRecovery(projectId, 120000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/confirm`,
        payload,
        { timeout: 120000 },
      ),
    );
  },

  workflowAction(
    projectId: string,
    action: PharmaWorkflowAction,
    data: Record<string, unknown> = {},
    comment = "",
  ) {
    return withProjectRecovery(projectId, 240000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/workflow/actions`,
        { action, data, comment },
        { timeout: 240000 },
      ),
    );
  },

  generateDimensions(
    projectId: string,
    payload: {
      kbIds?: string[];
      kbNames?: string[];
      searchMode?: "auto" | "none" | "standard" | "deep";
      searchPlatforms?: string[];
    } = {},
  ) {
    return withProjectRecovery(projectId, 240000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/dimensions/generate`,
        {
          kb_ids: payload.kbIds || [],
          kb_names: payload.kbNames || [],
          search_mode: payload.searchMode || "auto",
          search_platforms: payload.searchPlatforms || [],
        },
        { timeout: 240000 },
      ),
    );
  },

  uploadLiterature(
    projectId: string,
    payload: { docKind: string; files: File[] },
  ) {
    const form = new FormData();
    form.append("doc_kind", payload.docKind);
    payload.files.forEach((file) => form.append("files", file));
    return apiV1Client.post<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/literature`,
      form,
      { timeout: 150000 },
    );
  },

  deleteLiterature(projectId: string, docId: string) {
    return apiV1Client.delete<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/literature/${docId}`,
    );
  },

  matchLiterature(
    projectId: string,
    payload: { kbIds?: string[]; kbNames?: string[]; tier?: LiteratureTier },
  ) {
    return withProjectRecovery(projectId, 240000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/literature/match`,
        {
          kb_ids: payload.kbIds || [],
          kb_names: payload.kbNames || [],
          tier: payload.tier || "light",
        },
        { timeout: 240000 },
      ),
    );
  },

  exportLiteratureTripleTable(projectId: string) {
    return apiV1Client.get(
      `/pharma-translator/projects/${projectId}/literature/triple-table.csv`,
      { responseType: "blob" },
    );
  },

  literatureRedlines(projectId?: string) {
    return apiV1Client.get<
      Envelope<{ items: PharmaLiteratureRedline[]; total: number }>
    >("/pharma-translator/literature/redlines", {
      params: projectId ? { project_id: projectId } : {},
    });
  },

  importUserVoices(
    projectId: string,
    voices: Array<{ text: string; source: string }>,
  ) {
    return apiV1Client.post<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/user-voices`,
      { voices },
    );
  },

  deleteUserVoice(projectId: string, voiceId: string) {
    return apiV1Client.delete<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/user-voices/${voiceId}`,
    );
  },

  competitorCapabilities() {
    return apiV1Client.get<Envelope<CompetitorCapabilities>>(
      "/pharma-translator/competitor/capabilities",
    );
  },

  scanCompetitors(
    projectId: string,
    payload: {
      mode: CompetitorMode;
      platforms: string[];
      keywords: string[];
      brands: string[];
      urls: string[];
      per_keyword: number;
    },
  ) {
    return withProjectRecovery(projectId, 300000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/competitor/scan`,
        payload,
        { timeout: 300000 },
      ),
    );
  },

  analyzeCompetitors(projectId: string, payload: { our_price?: string } = {}) {
    return withProjectRecovery(projectId, 330000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/competitor/analyze`,
        payload,
        { timeout: 330000 },
      ),
    );
  },

  generateContentBatch(
    projectId: string,
    payload: { channels: string[]; total: number },
  ) {
    return withProjectRecovery(projectId, 900000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/content-batch/generate`,
        payload,
        // 30-50 条按渠道分批并发生成，最长可达数轮模型调用
        { timeout: 900000 },
      ),
    );
  },

  reworkContentChannel(
    projectId: string,
    payload: { channel: string; reason: string; comment: string },
  ) {
    return runContentJob(projectId, "rework", payload, 330000, "返工");
  },

  autoFixContent(projectId: string) {
    return runContentJob(projectId, "auto-fix", {}, 240000, "一键修复");
  },

  updateContentTopics(
    projectId: string,
    topics: Array<{ no: number; selected: boolean; publish_time: string }>,
  ) {
    return apiV1Client.post<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/content-batch/topics`,
      { topics },
    );
  },

  generateContentImages(
    projectId: string,
    payload: { content_id: string; indexes?: number[] },
  ) {
    return withProjectRecovery(projectId, 900000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/content-batch/images`,
        payload,
        // 逐张调用配图模型，6 张图可能需要数分钟
        { timeout: 900000 },
      ),
    );
  },

  complianceKnowledgeBase() {
    return apiV1Client.get<Envelope<ComplianceKnowledgeBase>>(
      "/pharma-translator/compliance/knowledge-base",
    );
  },

  runComplianceReview(
    projectId: string,
    payload: { kbIds?: string[]; kbNames?: string[]; aiSearch?: boolean },
  ) {
    return withProjectRecovery(projectId, 600000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/compliance/review`,
        {
          kb_ids: payload.kbIds || [],
          kb_names: payload.kbNames || [],
          ai_search: payload.aiSearch ?? true,
        },
        { timeout: 600000 },
      ),
    );
  },

  complianceReviewProgress(projectId: string) {
    return apiV1Client.get<
      Envelope<{
        running: boolean;
        started_at: number | null;
        logs: { t: number; message: string }[];
        streams: Record<string, string>;
      }>
    >(`/pharma-translator/projects/${projectId}/compliance/review/progress`, {
      timeout: 10000,
    });
  },

  runComplianceFilter(
    projectId: string,
    payload: {
      kb_ids?: string[];
      kb_names?: string[];
      ai_search?: boolean;
      inventory?: FilterInventoryItem[];
    } = {},
  ) {
    return withProjectRecovery(projectId, 300000, () =>
      apiV1Client.post<Envelope<PharmaProject>>(
        `/pharma-translator/projects/${projectId}/compliance-filter/run`,
        {
          kb_ids: payload.kb_ids || [],
          kb_names: payload.kb_names || [],
          ai_search: payload.ai_search ?? true,
          ...(payload.inventory ? { inventory: payload.inventory } : {}),
        },
        { timeout: 300000 },
      ),
    );
  },

  createComplianceTicket(
    projectId: string,
    payload: { question: string; riskIds?: string[] },
  ) {
    return apiV1Client.post<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/compliance/expert-tickets`,
      { question: payload.question, risk_ids: payload.riskIds || [] },
    );
  },

  answerComplianceTicket(
    projectId: string,
    ticketId: string,
    payload: { answer: string; expertName: string },
  ) {
    return apiV1Client.post<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/compliance/expert-tickets/${ticketId}/answer`,
      { answer: payload.answer, expert_name: payload.expertName },
    );
  },

  askComplianceAi(projectId: string, question: string) {
    return apiV1Client.post<Envelope<ComplianceAiAnswer>>(
      `/pharma-translator/projects/${projectId}/compliance/ai-ask`,
      { question },
      { timeout: 300000 },
    );
  },

  exportKeywords(projectId: string) {
    return apiV1Client.get(
      `/pharma-translator/projects/${projectId}/keywords.csv`,
      { responseType: "blob" },
    );
  },

  exportDelivery(projectId: string) {
    return apiV1Client.get(
      `/pharma-translator/projects/${projectId}/delivery.json`,
      { responseType: "blob" },
    );
  },

  exportApproval(projectId: string, kind: PharmaApprovalExportKind) {
    return apiV1Client.get(
      `/pharma-translator/projects/${projectId}/exports/${kind}`,
      { responseType: "blob" },
    );
  },

  updatePublishStatus(
    projectId: string,
    updates: Array<{
      content_id: string;
      publish_status: PublishStatus;
      publish_url?: string;
    }>,
    comment = "",
  ) {
    return apiV1Client.post<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/contents/publish-status`,
      { updates, comment },
    );
  },

  recordPerformance(
    projectId: string,
    platform: string,
    records: Array<Record<string, string | number>>,
    comment = "",
  ) {
    return apiV1Client.post<Envelope<PharmaProject>>(
      `/pharma-translator/projects/${projectId}/performance`,
      { platform, records, comment },
    );
  },

  skuReuse(projectId: string) {
    return apiV1Client.get<Envelope<SkuReuseStatus>>(
      `/pharma-translator/projects/${projectId}/sku-reuse`,
    );
  },

  contentHits() {
    return apiV1Client.get<
      Envelope<{ items: Array<PerformanceRecord & { product_name?: string; hook?: string }> }>
    >("/pharma-translator/content-hits");
  },

  source(projectId: string) {
    return apiV1Client.get(`/pharma-translator/projects/${projectId}/source`, {
      responseType: "blob",
    });
  },

  contentImage(projectId: string, filename: string) {
    return apiV1Client.get(
      `/pharma-translator/projects/${projectId}/content-images/${encodeURIComponent(filename)}`,
      { responseType: "blob" },
    );
  },
};
