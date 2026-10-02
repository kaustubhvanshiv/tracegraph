import { useState, useCallback } from 'react';

/**
 * Manages bidirectional highlight state between GraphPanel and TimelinePanel.
 *
 * - Selecting a node in GraphPanel → all timeline events with that entity_id are highlighted.
 * - Selecting an event in TimelinePanel → all graph nodes referenced in that event's entity_ids are highlighted.
 */
export function useGraphTimelineSync() {
  /** entity_id highlighted by a graph node click */
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  /** event_id highlighted by a timeline row click */
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  /** entity_ids associated with the currently selected timeline event */
  const [selectedEventEntityIds, setSelectedEventEntityIds] = useState<string[]>([]);

  const onNodeSelected = useCallback((entityId: string | null) => {
    setSelectedEntityId(entityId);
    if (entityId === null) {
      setSelectedEventId(null);
      setSelectedEventEntityIds([]);
    }
  }, []);

  const onEventSelected = useCallback(
    (eventId: string | null, entityIds: string[]) => {
      setSelectedEventId(eventId);
      setSelectedEventEntityIds(entityIds);
      if (eventId === null) {
        setSelectedEntityId(null);
      }
    },
    []
  );

  const clearSelection = useCallback(() => {
    setSelectedEntityId(null);
    setSelectedEventId(null);
    setSelectedEventEntityIds([]);
  }, []);

  return {
    selectedEntityId,
    selectedEventId,
    selectedEventEntityIds,
    onNodeSelected,
    onEventSelected,
    clearSelection,
  };
}
