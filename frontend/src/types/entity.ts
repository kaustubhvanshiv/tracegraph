export type EntityType = 'User' | 'Host' | 'Server' | 'IP' | 'Process' | 'File';

export interface Entity {
  entity_id: string;
  entity_type: EntityType;
  canonical_key: string;
  aliases: string[];
  event_ids: string[];
  investigation_id: string;
}
