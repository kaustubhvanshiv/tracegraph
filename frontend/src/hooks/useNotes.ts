import { useState, useCallback } from 'react';
import { notesApi } from '../services';
import { InvestigationNote } from '../types';

export const useNotes = (investigationId: string) => {
  const [notes, setNotes] = useState<InvestigationNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await notesApi.list(investigationId);
      // Sort notes newest first if backend doesn't already, or just keep backend order
      setNotes(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch notes');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const addNote = useCallback(async (body: string) => {
    setError(null);
    try {
      // Optimistic update could be done here, but let's just wait for backend response
      const response = await notesApi.create(investigationId, body);
      setNotes(prev => [response.data, ...prev]);
      return response.data;
    } catch (err: any) {
      setError(err.message || 'Failed to add note');
      return null;
    }
  }, [investigationId]);

  return {
    notes,
    loading,
    error,
    fetchNotes,
    addNote
  };
};
