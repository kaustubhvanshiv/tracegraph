import { useState, useCallback } from 'react';
import { investigationsApi } from '../services/investigationsApi';
import type {
  Investigation,
  Note,
  CreateInvestigationPayload,
  PatchInvestigationPayload,
  NotePayload,
} from '../types';

export function useInvestigation(investigationId?: string) {
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInvestigation = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await investigationsApi.get(id);
      setInvestigation(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load investigation');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchNotes = useCallback(async (id: string) => {
    try {
      const data = await investigationsApi.getNotes(id);
      setNotes(data);
    } catch {
      // non-critical
    }
  }, []);

  const patch = useCallback(
    async (payload: PatchInvestigationPayload): Promise<void> => {
      const targetId = investigationId || investigation?.investigation_id;
      if (!targetId) return;
      const updated = await investigationsApi.patch(targetId, payload);
      setInvestigation(updated);
    },
    [investigationId, investigation]
  );

  const addNote = useCallback(
    async (payload: NotePayload): Promise<Note> => {
      const targetId = investigationId || investigation?.investigation_id;
      if (!targetId) throw new Error('No investigation id');
      const note = await investigationsApi.addNote(targetId, payload);
      setNotes((prev) => [...prev, note]);
      return note;
    },
    [investigationId, investigation]
  );

  return {
    investigation,
    notes,
    loading,
    error,
    fetchInvestigation,
    fetchNotes,
    patch,
    addNote,
  };
}

export function useInvestigationList() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await investigationsApi.list({ limit: 100 });
      setInvestigations(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load investigations');
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(
    async (payload: CreateInvestigationPayload): Promise<Investigation> => {
      const inv = await investigationsApi.create(payload);
      setInvestigations((prev) => [inv, ...prev]);
      return inv;
    },
    []
  );

  return { investigations, loading, error, fetch, create };
}
