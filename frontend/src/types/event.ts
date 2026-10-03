import type { Entity } from './entity';
import type { CorrelatedRelationship } from './relationship';

export type Severity = 'low' | 'medium' | 'high' | 'critical';

export interface SecurityEvent {
  event_id: string;
  source_type: string;
  timestamp: string;
  event_type: string;
  action: string;
  user: string | null;
  source_host: string | null;
  destination_host: string | null;
  source_ip: string | null;
  destination_ip: string | null;
  process: string | null;
  file: string | null;
  severity: Severity | null;
  raw_data: Record<string, unknown> | null;
}

export interface TimelineEvent {
  event: SecurityEvent;
  entity_ids: string[];
}

export interface TimelineResult {
  investigation_id: string;
  events: TimelineEvent[];
  total: number;
}

export interface CorrelationMetadata {
  relationship_id: string;
  signal_names: string[];
  signal_scores: Record<string, number>;
  combined_score: number;
  explanation: string;
}

export interface EvidenceDetail {
  event: SecurityEvent;
  raw_data: Record<string, unknown> | null;
  entities: Entity[];
  relationships: CorrelatedRelationship[];
  correlation_metadata: CorrelationMetadata[];
}

export interface IngestionResponse {
  accepted: number;
  rejected: number;
  errors: Array<{ event_id: string | null; reason: string; field: string | null }>;
  timing_metrics: Record<string, number>;
}
