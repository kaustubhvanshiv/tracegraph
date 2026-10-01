import React, { useEffect, useState } from 'react';
import { useNotes } from '../../hooks/useNotes';
import { useInvestigation } from '../../hooks/useInvestigation';
import { Investigation, InvestigationStatus, InvestigationOutcome } from '../../types';
import { formatUtc } from '../../utils/timelineHelpers';

interface AnalystDecisionPanelProps {
  investigation: Investigation;
  onInvestigationUpdated: (inv: Investigation) => void;
}

export const AnalystDecisionPanel: React.FC<AnalystDecisionPanelProps> = ({ 
  investigation, 
  onInvestigationUpdated 
}) => {
  const { notes, loading: notesLoading, error: notesError, fetchNotes, addNote } = useNotes(investigation.investigation_id);
  const { updateStatus, loading: updateLoading, error: updateError } = useInvestigation();
  
  const [newNote, setNewNote] = useState('');
  const [status, setStatus] = useState<InvestigationStatus>(investigation.status);
  const [outcome, setOutcome] = useState<InvestigationOutcome | ''>(investigation.outcome || '');

  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  useEffect(() => {
    setStatus(investigation.status);
    setOutcome(investigation.outcome || '');
  }, [investigation]);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim()) return;
    
    const note = await addNote(newNote);
    if (note) {
      setNewNote('');
    }
  };

  const handleUpdateStatus = async () => {
    const updated = await updateStatus(
      investigation.investigation_id, 
      status, 
      outcome === '' ? undefined : outcome
    );
    if (updated) {
      onInvestigationUpdated(updated);
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="flex p-4 border-b border-gray-100 bg-gray-50/50 justify-between items-center">
        <h2 className="text-lg font-semibold text-gray-800">Analyst Decision</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
        
        {/* Status & Outcome Controls */}
        <section className="bg-blue-50/50 p-4 rounded-lg border border-blue-100">
          <h3 className="text-sm font-semibold text-blue-900 mb-3 uppercase tracking-wider">Resolution</h3>
          
          {updateError && (
            <div className="text-red-600 bg-red-50 p-2 rounded border border-red-200 text-sm mb-3">
              {updateError}
            </div>
          )}

          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Status</label>
              <select 
                value={status} 
                onChange={(e) => setStatus(e.target.value as InvestigationStatus)}
                className="border border-gray-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={InvestigationStatus.OPEN}>Open</option>
                <option value={InvestigationStatus.UNDER_REVIEW}>Under Review</option>
                <option value={InvestigationStatus.CLOSED}>Closed</option>
              </select>
            </div>
            
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Outcome</label>
              <select 
                value={outcome} 
                onChange={(e) => setOutcome(e.target.value as InvestigationOutcome | '')}
                className="border border-gray-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- Select Outcome --</option>
                <option value={InvestigationOutcome.TRUE_POSITIVE}>True Positive</option>
                <option value={InvestigationOutcome.FALSE_POSITIVE}>False Positive</option>
                <option value={InvestigationOutcome.INCONCLUSIVE}>Inconclusive</option>
                <option value={InvestigationOutcome.ESCALATED}>Escalated</option>
              </select>
            </div>

            <button 
              onClick={handleUpdateStatus}
              disabled={updateLoading || (status === investigation.status && outcome === (investigation.outcome || ''))}
              className="mt-2 w-full px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {updateLoading ? 'Updating...' : 'Save Resolution'}
            </button>
          </div>
        </section>

        {/* Analyst Notes Section */}
        <section className="flex flex-col flex-1">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wider">Analyst Notes</h3>
          
          <form onSubmit={handleAddNote} className="mb-4">
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="Add your investigation notes here..."
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-2 min-h-[80px]"
            />
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Markdown supported</span>
              <button 
                type="submit"
                disabled={!newNote.trim()}
                className="px-4 py-1.5 bg-gray-800 text-white text-sm font-medium rounded-md hover:bg-gray-900 transition-colors disabled:opacity-50"
              >
                Add Note
              </button>
            </div>
          </form>

          {notesError && (
            <div className="text-red-600 bg-red-50 p-2 rounded border border-red-200 text-sm mb-3">
              {notesError}
            </div>
          )}

          <div className="flex-1 overflow-y-auto space-y-3 pr-2">
            {notesLoading && notes.length === 0 && (
              <div className="text-center py-4 text-sm text-gray-500">Loading notes...</div>
            )}
            
            {!notesLoading && notes.length === 0 && (
              <div className="text-center py-8 text-sm text-gray-500 italic bg-gray-50 rounded border border-gray-100">
                No notes added yet.
              </div>
            )}

            {notes.map(note => (
              <div key={note.note_id} className="bg-yellow-50/80 border border-yellow-200/60 rounded-lg p-3">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-semibold text-xs text-yellow-800">Analyst</span>
                  <span className="text-[10px] text-yellow-600">{formatUtc(note.created_at)}</span>
                </div>
                <div className="text-sm text-gray-800 whitespace-pre-wrap">
                  {note.body}
                </div>
              </div>
            ))}
          </div>
        </section>

      </div>
    </div>
  );
};
