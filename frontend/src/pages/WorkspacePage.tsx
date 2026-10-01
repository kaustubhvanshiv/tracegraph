import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  GraphPanel, 
  TimelinePanel, 
  EvidencePanel, 
  AISummaryPanel, 
  AnalystDecisionPanel 
} from '../components/Workspace';
import { useGraphTimelineSync } from '../hooks/useGraphTimelineSync';
import { useInvestigation } from '../hooks/useInvestigation';
import { Investigation } from '../types';

const WorkspacePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const { getInvestigation, loading, error } = useInvestigation();
  
  const { 
    selectedEvent,
    handleNodeSelect,
    handleEventSelect,
    graphHighlightedEntityIds,
    timelineHighlightedEntityId
  } = useGraphTimelineSync();

  useEffect(() => {
    if (id) {
      getInvestigation(id).then(data => {
        if (data) setInvestigation(data);
      });
    }
  }, [id, getInvestigation]);

  if (loading && !investigation) {
    return <div className="p-8 flex justify-center items-center h-screen">Loading workspace...</div>;
  }

  if (error || !investigation) {
    return (
      <div className="p-8 flex flex-col items-center justify-center h-screen">
        <h1 className="text-2xl font-bold text-red-600 mb-4">Error loading workspace</h1>
        <p className="text-gray-600 mb-4">{error || 'Investigation not found'}</p>
        <Link to="/investigations" className="text-blue-600 hover:underline">Back to Investigations</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-100 overflow-hidden">
      {/* Workspace Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex justify-between items-center shrink-0 shadow-sm z-10">
        <div className="flex items-center gap-4">
          <Link to="/investigations" className="text-gray-500 hover:text-blue-600 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{investigation.title}</h1>
            <p className="text-sm text-gray-500">ID: {investigation.investigation_id}</p>
          </div>
        </div>
        <div>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold
            ${investigation.status === 'OPEN' ? 'bg-green-100 text-green-800' : ''}
            ${investigation.status === 'UNDER_REVIEW' ? 'bg-yellow-100 text-yellow-800' : ''}
            ${investigation.status === 'CLOSED' ? 'bg-gray-100 text-gray-800' : ''}
          `}>
            {investigation.status}
          </span>
        </div>
      </header>

      {/* Workspace Grid */}
      <main className="flex-1 overflow-hidden p-4 gap-4 grid grid-cols-12 grid-rows-2">
        
        {/* Left Column: Graph & Summaries */}
        <div className="col-span-8 row-span-2 flex flex-col gap-4 overflow-hidden">
          {/* Top Half: Graph */}
          <div className="flex-1 min-h-0">
            <GraphPanel 
              investigationId={investigation.investigation_id} 
              onNodeSelect={handleNodeSelect}
              highlightedEntityIds={graphHighlightedEntityIds}
            />
          </div>
          
          {/* Bottom Half: AI Summary and Analyst Decision side by side */}
          <div className="flex-1 min-h-0 grid grid-cols-2 gap-4">
            <div className="overflow-hidden">
              <AISummaryPanel investigationId={investigation.investigation_id} />
            </div>
            <div className="overflow-hidden">
              <AnalystDecisionPanel 
                investigation={investigation} 
                onInvestigationUpdated={setInvestigation} 
              />
            </div>
          </div>
        </div>

        {/* Right Column: Timeline & Evidence */}
        <div className="col-span-4 row-span-2 flex flex-col gap-4 overflow-hidden">
          {/* Top Half: Timeline */}
          <div className="flex-1 min-h-0">
            <TimelinePanel 
              investigationId={investigation.investigation_id} 
              selectedEntityId={timelineHighlightedEntityId}
              onEventSelect={handleEventSelect}
            />
          </div>
          
          {/* Bottom Half: Evidence */}
          <div className="flex-1 min-h-0">
            <EvidencePanel 
              investigationId={investigation.investigation_id} 
              selectedEventId={selectedEvent?.event_id || null}
            />
          </div>
        </div>

      </main>
    </div>
  );
};

export default WorkspacePage;
