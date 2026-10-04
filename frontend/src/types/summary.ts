export interface SummaryResult {
  overview: string;
  chronological_sequence: string[];
  key_entities: string[];
  key_relationships: string[];
  evidence_refs: string[];
  uncertainty: string;
  next_questions: string[];
  error_flag: boolean;
  error_message: string | null;
}
