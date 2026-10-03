export type InvestigationStatus = 'OPEN' | 'UNDER_REVIEW' | 'CLOSED';
export type InvestigationOutcome =
  | 'TRUE_POSITIVE'
  | 'FALSE_POSITIVE'
  | 'INCONCLUSIVE'
  | 'ESCALATED';

export interface Investigation {
  investigation_id: string;
  title: string;
  description: string | null;
  status: InvestigationStatus;
  outcome: string | null;
  created_at: string;
  updated_at: string;
  owner_id: string;
  event_count: number;
}

export interface Note {
  note_id: string;
  investigation_id: string;
  author_id: string;
  body: string;
  created_at: string;
}

export interface CreateInvestigationPayload {
  title: string;
  description?: string;
}

export interface PatchInvestigationPayload {
  status?: InvestigationStatus;
  outcome?: InvestigationOutcome;
}

export interface NotePayload {
  body: string;
}
