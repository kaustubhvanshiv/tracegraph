import { apiClient, unwrap } from './client';
import type { GraphResult, EntityDetail, EntityType, RelationshipType } from '../types';

export const graphApi = {
  getGraph: async (
    investigationId: string,
    params?: {
      entity_type?: EntityType;
      relationship_type?: RelationshipType;
      start_time?: string;
      end_time?: string;
    }
  ): Promise<GraphResult> => {
    const { data } = await apiClient.get(
      `/api/investigations/${investigationId}/graph`,
      { params }
    );
    return unwrap(data);
  },

  pivot: async (
    investigationId: string,
    entityId: string,
    hops = 2
  ): Promise<GraphResult> => {
    const { data } = await apiClient.get(
      `/api/investigations/${investigationId}/graph/pivot`,
      { params: { entity_id: entityId, hops } }
    );
    return unwrap(data);
  },

  getEntity: async (
    investigationId: string,
    entityId: string
  ): Promise<EntityDetail> => {
    const { data } = await apiClient.get(
      `/api/investigations/${investigationId}/entities/${entityId}`
    );
    return unwrap(data);
  },
};
