import React, { useEffect } from 'react';
import { useSummary } from '../../hooks/useSummary';

interface AISummaryPanelProps {
  investigationId: string;
}

export const AISummaryPanel: React.FC<AISummaryPanelProps> = ({ investigationId }) => {
  const { data, loading, error, fetchSummary, generateSummary } = useSummary(investigationId);

  useEffect(() => {
    // Attempt to fetch cached summary on mount
    fetchSummary();
  }, [fetchSummary]);

  return (
    <div className="flex flex-col h-full w-full bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="flex justify-between items-center p-4 border-b border-gray-100 bg-gray-50/50">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
          </svg>
          AI Summary
        </h2>
        <button 
          onClick={() => generateSummary(true)} 
          disabled={loading}
          className="text-sm px-3 py-1.5 bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 rounded-md shadow-sm transition-colors disabled:opacity-50"
        >
          {loading ? 'Generating...' : 'Regenerate'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto relative p-5">
        {loading && !data && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 z-10 gap-3">
            <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-gray-600 font-medium">Analyzing investigation graph...</p>
          </div>
        )}

        {error && error.isUnavailable && (
          <div className="bg-yellow-50 text-yellow-800 p-4 rounded-lg border border-yellow-200 mb-4">
            <h3 className="font-semibold mb-1 flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
              AI Service Unavailable
            </h3>
            <p className="text-sm">The AI summarization service is currently offline or unconfigured. You can continue your investigation using the Graph and Timeline panels.</p>
          </div>
        )}

        {error && !error.isUnavailable && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200 mb-4">
            <p className="font-semibold">Error</p>
            <p className="text-sm">{error.message}</p>
          </div>
        )}

        {!data && !loading && !error && (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-sm mx-auto">
            <p className="text-gray-500 mb-4">No AI summary has been generated for this investigation yet.</p>
            <button 
              onClick={() => generateSummary()}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg shadow-sm transition-colors"
            >
              Generate AI Summary
            </button>
          </div>
        )}

        {data && (
          <div className="space-y-6 animate-fade-in">
            {data.error_flag && (
              <div className="bg-orange-50 text-orange-800 p-3 rounded border border-orange-200 text-sm">
                <strong>Notice:</strong> {data.error_message || 'The AI encountered an issue and produced a partial or degraded summary.'}
              </div>
            )}

            <div>
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Executive Summary</h3>
              <div className="prose prose-sm max-w-none text-gray-800 whitespace-pre-wrap">
                {data.summary || 'No summary available.'}
              </div>
            </div>

            {data.uncertainty && (
              <div className="bg-blue-50/50 p-4 rounded-lg border border-blue-100">
                <h3 className="text-sm font-semibold text-blue-800 uppercase tracking-wider mb-2">Confidence & Uncertainty</h3>
                <div className="text-sm text-blue-900 whitespace-pre-wrap">
                  {data.uncertainty}
                </div>
              </div>
            )}

            {data.evidence_refs && data.evidence_refs.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Referenced Evidence IDs</h3>
                <div className="flex flex-wrap gap-2">
                  {data.evidence_refs.map(ref => (
                    <span key={ref} className="px-2 py-1 bg-gray-100 border border-gray-200 text-gray-600 rounded text-xs font-mono">
                      {ref}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
