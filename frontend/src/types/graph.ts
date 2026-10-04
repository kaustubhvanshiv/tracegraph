import type { Entity } from './entity';
import type { CorrelatedRelationship } from './relationship';

export interface GraphResult {
  investigation_id: string;
  nodes: Entity[];
  edges: CorrelatedRelationship[];
}

export interface EntityDetail {
  entity: Entity;
  relationships: CorrelatedRelationship[];
  event_ids: string[];
}
