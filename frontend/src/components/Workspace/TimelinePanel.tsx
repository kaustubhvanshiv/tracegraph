import React, { useEffect, useState } from 'react';
import { useTimeline } from '../../hooks/useTimeline';
import { formatUtc } from '../../utils/timelineHelpers';
import { TimelineEvent } from '../../types';

interface TimelinePanelProps {
  investigationId: string;
  selectedEntityId?: string | null;
  onEventSelect?: (event: TimelineEvent) => void;
}

export const TimelinePanel: React.FC<TimelinePanelProps> = ({ 
  investigationId, 
  selectedEntityId, 
  onEventSelect 
}) => {
  const { data, loading, error, fetchTimeline } = useTimeline(investigationId);
  const [severityFilter, setSeverityFilter] = useState<string>('');

  useEffect(() => {
    // Re-fetch timeline when selectedEntityId changes to filter by entity
    fetchTimeline({ 
      entity_id: selectedEntityId || undefined,
      severity: severityFilter || undefined
    });
  }, [fetchTimeline, selectedEntityId, severityFilter]);

  const severityColors = {
    low: 'bg-green-100 text-green-800 border-green-200',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    high: 'bg-orange-100 text-orange-800 border-orange-200',
    critical: 'bg-red-100 text-red-800 border-red-200',
  };

  return (
    <div className="flex flex-col h-full w-full bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="flex flex-col gap-3 p-4 border-b border-gray-100 bg-gray-50/50">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-800">Timeline</h2>
          <span className="text-sm text-gray-500 font-medium">
            {data?.total || 0} events
          </span>
        </div>
        
        <div className="flex gap-2 text-sm">
          <select 
            value={severityFilter} 
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          {selectedEntityId && (
            <div className="flex items-center px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-100">
              <span className="truncate max-w-[150px]">Filtered by entity</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/50 z-10">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
        )}

        {error && (
          <div className="text-red-600 bg-red-50 p-3 rounded border border-red-200 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {data?.events.map((event) => (
            <div 
              key={event.event_id}
              onClick={() => onEventSelect && onEventSelect(event)}
              className="flex gap-4 p-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50/30 cursor-pointer transition-colors relative"
            >
              {/* Timeline connecting line (visual only, simplified) */}
              <div className="flex flex-col items-center pt-1">
                <div className={`w-3 h-3 rounded-full ${severityColors[event.severity] || 'bg-gray-200'}`}></div>
                <div className="w-0.5 h-full bg-gray-100 mt-1 absolute top-5 bottom-[-16px]"></div>
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-semibold text-gray-800 truncate">{event.event_type}</span>
                  <span className="text-xs text-gray-500 whitespace-nowrap ml-2">
                    {formatUtc(event.timestamp)}
                  </span>
                </div>
                <div className="text-sm text-gray-600 mb-2 truncate">
                  {event.action} | {event.source_type}
                </div>
                
                <div className="flex flex-wrap gap-1 mt-1">
                  {event.user && <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded truncate max-w-[120px]">User: {event.user}</span>}
                  {event.source_host && <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded truncate max-w-[120px]">Src: {event.source_host}</span>}
                  {event.destination_host && <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded truncate max-w-[120px]">Dst: {event.destination_host}</span>}
                </div>
              </div>
            </div>
          ))}
          
          {!loading && data?.events.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              No events found.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
