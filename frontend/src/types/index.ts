export interface SuccessResponse<T> {
  success: true;
  data: T;
}

export interface ErrorDetail {
  loc?: (string | number)[];
  msg: string;
  type: string;
}

export interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: ErrorDetail[];
  };
}

export enum InvestigationStatus {
  OPEN = 'OPEN',
  UNDER_REVIEW = 'UNDER_REVIEW',
  CLOSED = 'CLOSED',
}

export enum InvestigationOutcome {
  TRUE_POSITIVE = 'TRUE_POSITIVE',
  FALSE_POSITIVE = 'FALSE_POSITIVE',
  INCONCLUSIVE = 'INCONCLUSIVE',
  ESCALATED = 'ESCALATED',
}

export interface Investigation {
  investigation_id: string;
  title: string;
  description?: string | null;
  status: InvestigationStatus;
  outcome?: InvestigationOutcome | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface InvestigationNote {
  note_id: string;
  investigation_id: string;
  body: string;
  author_id: string;
  created_at: string;
}

// Security Event types
export interface SecurityEvent {
  event_id: string;
  source_type: string;
  timestamp: string;
  event_type: string;
  action: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  user?: string | null;
  source_host?: string | null;
  destination_host?: string | null;
  source_ip?: string | null;
  destination_ip?: string | null;
  process?: string | null;
  file?: string | null;
  raw_data?: Record<string, any>;
}

// Graph types
export interface Entity {
  entity_id: string;
  entity_type: string;
  canonical_key: string;
  aliases: string[];
}

export interface Relationship {
  source_id: string;
  target_id: string;
  type: string;
  investigation_id: string;
  event_ids: string[];
  signal_names: string[];
  combined_score: number;
  explanation: string;
  timestamp: string;
  source: string;
}

export interface GraphResult {
  investigation_id: string;
  nodes: Entity[];
  edges: Relationship[];
}

// Timeline types
export interface TimelineEvent extends SecurityEvent {
  entity_ids: string[];
}

export interface TimelineResult {
  events: TimelineEvent[];
  total: number;
}

// Evidence types
export interface EvidenceDetail {
  event: SecurityEvent;
  extracted_entities: Entity[];
  relationships: Relationship[];
}

// Summary types
export interface SummaryResult {
  summary?: string;
  uncertainty?: string;
  evidence_refs?: string[];
  error_flag: boolean;
  error_message?: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
