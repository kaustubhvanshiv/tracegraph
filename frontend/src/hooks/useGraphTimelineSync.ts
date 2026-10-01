import { useState, useCallback } from 'react';
import { TimelineEvent } from '../types';

export const useGraphTimelineSync = () => {
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);

  const handleNodeSelect = useCallback((entityId: string | null) => {
    setSelectedEntityId(entityId);
    // If the node selection changes, we don't necessarily clear the event, 
    // but the graph selection will drive highlighting in the timeline.
  }, []);

  const handleEventSelect = useCallback((event: TimelineEvent | null) => {
    setSelectedEvent(event);
    // When an event is selected, we could also automatically select the primary entity, 
    // but usually it's better to just pass the event to the GraphPanel for highlighting its entities.
  }, []);

  // Compute derived state for what should be highlighted in the graph
  const graphHighlightedEntityIds = selectedEvent ? selectedEvent.entity_ids : (selectedEntityId ? [selectedEntityId] : []);

  // For the timeline, we just pass the selectedEntityId so it can highlight matching events
  const timelineHighlightedEntityId = selectedEntityId;

  return {
    selectedEntityId,
    selectedEvent,
    handleNodeSelect,
    handleEventSelect,
    graphHighlightedEntityIds,
    timelineHighlightedEntityId
  };
};
