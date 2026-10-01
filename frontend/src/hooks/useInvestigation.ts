import { useState, useCallback } from 'react';
import { investigationsApi } from '../services';
import { Investigation, InvestigationStatus, InvestigationOutcome } from '../types';

export const useInvestigation = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const listInvestigations = useCallback(async (limit = 50, offset = 0): Promise<Investigation[] | null> => {
    setLoading(true);
    setError(null);
    try {
      const response = await investigationsApi.list(limit, offset);
      return response.data;
    } catch (err: any) {
      setError(err.message || 'Failed to list investigations');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const getInvestigation = useCallback(async (id: string): Promise<Investigation | null> => {
    setLoading(true);
    setError(null);
    try {
      const response = await investigationsApi.get(id);
      return response.data;
    } catch (err: any) {
      setError(err.message || 'Failed to get investigation');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const createInvestigation = useCallback(async (title: string, description: string): Promise<Investigation | null> => {
    setLoading(true);
    setError(null);
    try {
      const response = await investigationsApi.create({ title, description });
      return response.data;
    } catch (err: any) {
      setError(err.message || 'Failed to create investigation');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const updateStatus = useCallback(async (
    id: string, 
    status: InvestigationStatus, 
    outcome?: InvestigationOutcome
  ): Promise<Investigation | null> => {
    setLoading(true);
    setError(null);
    try {
      const response = await investigationsApi.updateStatus(id, status, outcome);
      return response.data;
    } catch (err: any) {
      setError(err.message || 'Failed to update status');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    listInvestigations,
    getInvestigation,
    createInvestigation,
    updateStatus,
  };
};
