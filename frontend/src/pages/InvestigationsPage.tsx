import React, { useEffect, useState } from 'react';
import { useInvestigation } from '../hooks/useInvestigation';
import { InvestigationList } from '../components/InvestigationList';
import { Investigation } from '../types';

const InvestigationsPage: React.FC = () => {
  const { listInvestigations, createInvestigation, loading, error } = useInvestigation();
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  
  // Form state
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [formLoading, setFormLoading] = useState(false);

  useEffect(() => {
    loadInvestigations();
  }, [listInvestigations]);

  const loadInvestigations = async () => {
    const data = await listInvestigations();
    if (data) {
      setInvestigations(data);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormLoading(true);
    const newInv = await createInvestigation(title, description);
    setFormLoading(false);
    if (newInv) {
      setIsFormOpen(false);
      setTitle('');
      setDescription('');
      loadInvestigations(); // Reload the list
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Investigations</h1>
        <button
          onClick={() => setIsFormOpen(!isFormOpen)}
          className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
        >
          {isFormOpen ? 'Cancel' : 'New Investigation'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6 border border-red-200">
          {error}
        </div>
      )}

      {isFormOpen && (
        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200 mb-8">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">Create New Investigation</h2>
          <form onSubmit={handleCreate}>
            <div className="mb-4">
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                Title
              </label>
              <input
                type="text"
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g. Suspicious lateral movement"
              />
            </div>
            <div className="mb-6">
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                placeholder="Brief details about the incident..."
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setIsFormOpen(false)}
                className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={formLoading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {formLoading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      <InvestigationList investigations={investigations} loading={loading && investigations.length === 0} />
    </div>
  );
};

export default InvestigationsPage;
