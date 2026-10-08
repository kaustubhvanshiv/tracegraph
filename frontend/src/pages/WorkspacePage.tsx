import { useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import WorkspaceHeader from '../components/Workspace/Header';
import GraphPanel from '../components/Workspace/GraphPanel';
import TimelinePanel from '../components/Workspace/TimelinePanel';
import EvidencePanel from '../components/Workspace/EvidencePanel';
import AISummaryPanel from '../components/Workspace/AISummaryPanel';
import AnalystDecisionPanel from '../components/Workspace/AnalystDecisionPanel';
import { useGraph } from '../hooks/useGraph';
import { useTimeline } from '../hooks/useTimeline';
import { useInvestigation } from '../hooks/useInvestigation';
import { useGraphTimelineSync } from '../hooks/useGraphTimelineSync';

export default function WorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const investigationId = id ?? '';

  const { investigation, notes, fetchInvestigation, fetchNotes, patch, addNote } =
    useInvestigation(investigationId);

  const { graph, loading: graphLoading, error: graphError, fetchGraph } =
    useGraph(investigationId);

  const {
    timeline,
    evidence,
    loading: timelineLoading,
    evidenceLoading,
    error: timelineError,
    fetchTimeline,
    fetchEvidence,
  } = useTimeline(investigationId);

  const {
    selectedEntityId,
    selectedEventId,
    selectedEventEntityIds,
    onNodeSelected,
    onEventSelected,
  } = useGraphTimelineSync();

  // Refs to trigger summary regeneration from header
  const summaryTriggerRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!investigationId) return;
    fetchInvestigation(investigationId);
    fetchNotes(investigationId);
    fetchGraph();
    fetchTimeline();
  }, [investigationId, fetchInvestigation, fetchNotes, fetchGraph, fetchTimeline]);

  // When timeline event selected → fetch its evidence
  useEffect(() => {
    if (selectedEventId) fetchEvidence(selectedEventId);
  }, [selectedEventId, fetchEvidence]);

  const handleEventSelected = (eventId: string | null, entityIds: string[]) => {
    onEventSelected(eventId, entityIds);
  };

  const handleEvidenceRefClick = (eventId: string) => {
    onEventSelected(eventId, []);
    fetchEvidence(eventId);
  };

  const handleFilterChange = useCallback(
    (params: { event_type?: string; entity_id?: string }) => {
      fetchTimeline(params);
    },
    [fetchTimeline]
  );

  const handleGenerateSummary = () => {
    summaryTriggerRef.current?.();
  };

  return (
    <div className="h-screen flex flex-col bg-surface overflow-hidden">
      <WorkspaceHeader
        investigation={investigation}
        onGenerateSummary={handleGenerateSummary}
      />

      {/* Responsive workspace layout */}
      <div className="flex-1 grid gap-3 p-3 overflow-hidden
        grid-cols-1
        md:grid-cols-2
        lg:grid-cols-5
        md:grid-rows-[auto_1fr]
        lg:grid-rows-[1fr]
        min-h-0">
        
        {/* Graph Panel - responsive positioning */}
        <div className="
          col-span-1
          md:col-span-2
          lg:col-span-3
          lg:row-span-1
          min-h-0
          lg:flex lg:flex-col
        ">
          <div className="min-h-0 lg:flex-[55]">
            <GraphPanel
              graph={graph}
              loading={graphLoading}
              error={graphError}
              selectedEntityId={selectedEntityId}
              highlightedEntityIds={selectedEventEntityIds}
              onNodeSelected={onNodeSelected}
            />
          </div>

          {/* Timeline Panel - below Graph on mobile/tablet, beside Graph on desktop */}
          <div className="
            col-span-1
            md:col-span-2
            lg:col-span-3
            lg:row-span-1
            min-h-0
            lg:flex-[45]
            mt-3 lg:mt-0
          ">
            <TimelinePanel
              timeline={timeline}
              loading={timelineLoading}
              error={timelineError}
              selectedEventId={selectedEventId}
              highlightedEntityId={selectedEntityId}
              onEventSelected={handleEventSelected}
              onFilterChange={handleFilterChange}
            />
          </div>
        </div>

        {/* Right Column: Evidence + AI Summary + Analyst Decision */}
        <div className="
          col-span-1
          md:col-span-2
          lg:col-span-2
          lg:row-span-1
          flex flex-col gap-3 min-h-0
          order-last md:order-none
        ">
          {/* Evidence: top third */}
          <div className="flex-1 min-h-0">
            <EvidencePanel evidence={evidence} loading={evidenceLoading} />
          </div>

          {/* AI Summary: middle third */}
          <div className="flex-1 min-h-0">
            <AISummaryPanel
              investigationId={investigationId}
              onEvidenceRefClick={handleEvidenceRefClick}
            />
          </div>

          {/* Analyst Decision: bottom third */}
          <div className="flex-1 min-h-0">
            <AnalystDecisionPanel
              investigation={investigation}
              notes={notes}
              onPatch={async (payload) => {
                await patch({ status: payload.status, outcome: payload.outcome as import('../types').InvestigationOutcome | undefined });
              }}
              onAddNote={async (body) => { await addNote({ body }); }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
