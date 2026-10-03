export type RelationshipType =
  | 'LOGGED_INTO'
  | 'AUTHENTICATED_TO'
  | 'EXECUTED'
  | 'CONNECTED_TO'
  | 'ACCESSED';

export interface CorrelatedRelationship {
  relationship_id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: RelationshipType;
  investigation_id: string;
  timestamp: string;
  event_ids: string[];
  source: string;
  signal_names: string[];
  signal_scores: Record<string, number>;
  /** [0.0, 1.0] — relevance indicator, NOT attack probability */
  combined_score: number;
  explanation: string;
}
