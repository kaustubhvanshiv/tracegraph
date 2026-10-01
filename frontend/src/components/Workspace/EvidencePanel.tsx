import React, { useEffect } from 'react';
import { useEvidence } from '../../hooks/useEvidence';
import { formatUtc } from '../../utils/timelineHelpers';

interface EvidencePanelProps {
  investigationId: string;
  selectedEventId: string | null;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ investigationId, selectedEventId }) => {
  const { data, loading, error, fetchEvidence } = useEvidence(investigationId);

  useEffect(() => {
    if (selectedEventId) {
      fetchEvidence(selectedEventId);
    }
  }, [fetchEvidence, selectedEventId]);

  if (!selectedEventId) {
    return (
      <div className="flex flex-col h-full w-full bg-gray-50 rounded-lg shadow-sm border border-gray-200 items-center justify-center">
        <p className="text-gray-500 font-medium">Select an event from the timeline to view evidence.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="flex p-4 border-b border-gray-100 bg-gray-50/50">
        <h2 className="text-lg font-semibold text-gray-800">Evidence Details</h2>
      </div>

      <div className="flex-1 overflow-y-auto relative p-4">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
        )}

        {error && (
          <div className="text-red-600 bg-red-50 p-3 rounded border border-red-200 text-sm mb-4">
            {error}
          </div>
        )}

        {data && !loading && (
          <div className="space-y-6">
            {/* Normalized Event Section */}
            <section>
              <h3 className="text-md font-semibold text-gray-700 border-b border-gray-200 pb-2 mb-3">Normalized Event</h3>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div><span className="font-medium text-gray-600">Event ID:</span> <span className="text-gray-800 break-all">{data.event.event_id}</span></div>
                <div><span className="font-medium text-gray-600">Timestamp:</span> <span className="text-gray-800">{formatUtc(data.event.timestamp)}</span></div>
                <div><span className="font-medium text-gray-600">Source Type:</span> <span className="text-gray-800">{data.event.source_type}</span></div>
                <div><span className="font-medium text-gray-600">Event Type:</span> <span className="text-gray-800">{data.event.event_type}</span></div>
                <div><span className="font-medium text-gray-600">Action:</span> <span className="text-gray-800">{data.event.action}</span></div>
                <div>
                  <span className="font-medium text-gray-600">Severity: </span> 
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    data.event.severity === 'critical' ? 'bg-red-100 text-red-800' :
                    data.event.severity === 'high' ? 'bg-orange-100 text-orange-800' :
                    data.event.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-green-100 text-green-800'
                  }`}>
                    {data.event.severity}
                  </span>
                </div>
                {data.event.user && <div><span className="font-medium text-gray-600">User:</span> <span className="text-gray-800">{data.event.user}</span></div>}
                {data.event.source_host && <div><span className="font-medium text-gray-600">Src Host:</span> <span className="text-gray-800">{data.event.source_host}</span></div>}
                {data.event.destination_host && <div><span className="font-medium text-gray-600">Dst Host:</span> <span className="text-gray-800">{data.event.destination_host}</span></div>}
                {data.event.source_ip && <div><span className="font-medium text-gray-600">Src IP:</span> <span className="text-gray-800">{data.event.source_ip}</span></div>}
                {data.event.destination_ip && <div><span className="font-medium text-gray-600">Dst IP:</span> <span className="text-gray-800">{data.event.destination_ip}</span></div>}
                {data.event.process && <div><span className="font-medium text-gray-600">Process:</span> <span className="text-gray-800 break-all">{data.event.process}</span></div>}
                {data.event.file && <div><span className="font-medium text-gray-600">File:</span> <span className="text-gray-800 break-all">{data.event.file}</span></div>}
              </div>
            </section>

            {/* Extracted Entities */}
            {data.extracted_entities.length > 0 && (
              <section>
                <h3 className="text-md font-semibold text-gray-700 border-b border-gray-200 pb-2 mb-3">Extracted Entities</h3>
                <div className="flex flex-wrap gap-2">
                  {data.extracted_entities.map(entity => (
                    <div key={entity.entity_id} className="bg-blue-50 border border-blue-100 rounded px-2 py-1 text-sm flex gap-2 items-center">
                      <span className="bg-blue-200 text-blue-800 text-xs px-1.5 py-0.5 rounded uppercase font-semibold">{entity.entity_type}</span>
                      <span className="text-blue-900 font-medium truncate max-w-[200px]" title={entity.canonical_key}>{entity.canonical_key}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Relationships & Correlations */}
            {data.relationships.length > 0 && (
              <section>
                <h3 className="text-md font-semibold text-gray-700 border-b border-gray-200 pb-2 mb-3">Relationships & Correlations</h3>
                <div className="space-y-3">
                  {data.relationships.map((rel, idx) => (
                    <div key={idx} className="bg-gray-50 border border-gray-200 rounded p-3 text-sm">
                      <div className="flex flex-wrap justify-between items-center mb-2 gap-2">
                        <span className="font-semibold text-gray-800 bg-gray-200 px-2 py-0.5 rounded">{rel.type}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-gray-500">Score:</span>
                          <span className="font-mono font-bold text-blue-600">{rel.combined_score.toFixed(2)}</span>
                        </div>
                      </div>
                      
                      {rel.explanation && (
                        <p className="text-gray-600 mb-2 italic">"{rel.explanation}"</p>
                      )}
                      
                      {rel.signal_names.length > 0 && (
                        <div>
                          <span className="text-xs text-gray-500 uppercase font-semibold block mb-1">Signals Fired:</span>
                          <div className="flex flex-wrap gap-1">
                            {rel.signal_names.map(signal => (
                              <span key={signal} className="bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded border border-purple-200">
                                {signal}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Raw Data */}
            {data.event.raw_data && (
              <section>
                <h3 className="text-md font-semibold text-gray-700 border-b border-gray-200 pb-2 mb-3">Raw Log</h3>
                <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                  <pre className="text-green-400 font-mono text-xs">
                    {JSON.stringify(data.event.raw_data, null, 2)}
                  </pre>
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
