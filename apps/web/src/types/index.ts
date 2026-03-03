/**
 * RYX — Types TypeScript partagés (frontend)
 * Mirrors des modèles Pydantic Python
 */

// ─── Claim ────────────────────────────────────────────────────────────────────

export type ClaimType = "reco" | "alert" | "score" | "dx" | "tx" | "info";
export type ClaimStatus = "pending" | "valid" | "blocked" | "needs_human";
export type CriticalityLevel = "low" | "moderate" | "high" | "critical";

export interface EvidenceRefBase {
  kind: string;
  confidence: number;
}

export interface DocEvidenceRef extends EvidenceRefBase {
  kind: "doc";
  doc_id: string;
  page: number;
  bbox: { x1: number; y1: number; x2: number; y2: number };
  snippet_text: string;
}

export interface DicomEvidenceRef extends EvidenceRefBase {
  kind: "dicom";
  study_id: string;
  series_id: string;
  instance_or_slice: string;
  roi?: { x1: number; y1: number; x2: number; y2: number };
}

export interface LabEvidenceRef extends EvidenceRefBase {
  kind: "lab";
  lab_id: string;
  test: string;
  value: number | string;
  unit?: string;
  date: string;
}

export interface KnowledgeEvidenceRef extends EvidenceRefBase {
  kind: "knowledge";
  knowledge_doc_id: string;
  chunk_id: string;
  excerpt: string;
  title?: string;
  source?: string;
}

export type EvidenceRef =
  | DocEvidenceRef
  | DicomEvidenceRef
  | LabEvidenceRef
  | KnowledgeEvidenceRef;

export interface Claim {
  claim_id: string;
  type: ClaimType;
  text: string;
  criticality: CriticalityLevel;
  evidence_refs: EvidenceRef[];
  status: ClaimStatus;
  blocked_reason?: string;
  created_at: string;
  validated_at?: string;
  validated_by?: string;
}

// ─── Patient ──────────────────────────────────────────────────────────────────

export interface Demographics {
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  dob_approximate?: boolean;
  sex?: string;
  phone?: string;
  address?: string;
}

export interface Patient {
  patient_id: string;
  demographics?: Demographics;
  identifiers: Array<{ type: string; value: string; issuer?: string }>;
  external_ids: Array<{ system: string; value: string; linked_at: string }>;
  quality_flags: string[];
  created_at: string;
  updated_at: string;
}

// ─── Encounter ────────────────────────────────────────────────────────────────

export interface Encounter {
  encounter_id: string;
  patient_id: string;
  start_at: string;
  end_at?: string;
  service?: string;
  reason?: string;
  location?: string;
  encounter_type: "inpatient" | "outpatient" | "emergency";
  status: "active" | "completed" | "cancelled";
}

// ─── Report ───────────────────────────────────────────────────────────────────

export interface ReportSections {
  summary?: string;
  timeline?: string;
  labs_trend?: string;
  imaging_findings?: string;
  active_problems: string[];
  medications: string[];
}

export interface Report {
  report_id: string;
  encounter_id: string;
  patient_id: string;
  generated_at: string;
  model_version: string;
  sections: ReportSections;
  recommendations: Claim[];
  questions: string[];
  claims: Claim[];
  overall_status: "complete" | "partial" | "blocked";
}

// ─── Prediction ───────────────────────────────────────────────────────────────

export type PredictionWindow = "30d" | "6m" | "1y" | "2y";
export type RiskBand = "low" | "moderate" | "high" | "critical";

export interface PredictionFactor {
  feature: string;
  contribution: number;
  direction: "positive" | "negative";
}

export interface Prediction {
  prediction_id: string;
  patient_id: string;
  model: string;
  model_version: string;
  window: PredictionWindow;
  score: number;
  band: RiskBand;
  top_factors: PredictionFactor[];
  claims: Claim[];
  computed_at: string;
}

// ─── Pagination ───────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

// ─── Notification ─────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  type: "alert" | "report_ready" | "job_completed" | "ops_incident";
  payload: {
    patient_id?: string;
    report_id?: string;
    message: string;
    criticality?: CriticalityLevel;
    created_at: string;
  };
  read: boolean;
  created_at: string;
}
