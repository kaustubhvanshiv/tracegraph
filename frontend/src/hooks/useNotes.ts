import { useState, useCallback } from 'react';
import { notesApi } from '../services/notesApi';
import type { Note } from '../types';

export const useNotes = (investigationId: string) => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await notesApi.list(investigationId);
      setNotes(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch notes');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const addNote = useCallback(async (body: string) => {
    setError(null);
    try {
      const data = await notesApi.create(investigationId, { body });
      setNotes((prev) => [data, ...prev]);
      return data;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add note');
      return null;
    }
  }, [investigationId]);

  return {
    notes,
    loading,
    error,
    fetchNotes,
    addNote,
  };
};
