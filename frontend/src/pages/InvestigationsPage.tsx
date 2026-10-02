import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInvestigationList } from '../hooks/useInvestigation';
import InvestigationList from '../components/InvestigationList/InvestigationList';
import type { InvestigationStatus } from '../types';

export default function InvestigationsPage() {
  const navigate = useNavigate();
  const { investigations, loading, error, fetch, create } = useInvestigationList();
  const [statusFilter, setStatusFilter] = useState<InvestigationStatus | undefined>(undefined);
  const [modalOpen, setModalOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => { fetch(); }, [fetch]);

  const filtered = statusFilter
    ? investigations.filter((i) => i.status === statusFilter)
    : investigations;

  const handleCreate = async () => {
    if (!title.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const inv = await create({ title: title.trim(), description: description.trim() || undefined });
      setModalOpen(false);
      setTitle('');
      setDescription('');
      navigate(`/investigations/${inv.investigation_id}`);
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create investigation');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface">
      {/* Nav */}
      <header className="bg-surface-low border-b border-outline-variant/20 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-primary text-xl" aria-hidden>🛡</span>
          <span className="text-lg font-bold text-on-surface tracking-tight">TraceGraph</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-on-surface-muted mono hidden md:block">SOC Investigation Platform</span>
          <button
            onClick={() => setModalOpen(true)}
            className="btn-primary flex items-center gap-1.5"
          >
            + New Investigation
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-on-surface">Investigations</h1>
          <p className="text-on-surface-muted mt-1">Track and manage security investigations</p>
        </div>

        <InvestigationList
          investigations={filtered}
          loading={loading}
          error={error}
          onStatusFilter={setStatusFilter}
        />
      </main>

      {/* Create modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-surface/80 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setModalOpen(false); }}
        >
          <div className="bg-surface-highest rounded-2xl p-6 w-full max-w-md shadow-sentinel-md">
            <h2 className="text-lg font-semibold text-on-surface mb-4">New Investigation</h2>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-on-surface-muted mb-1 block">Title *</label>
                <input
                  className="input-ghost w-full"
                  placeholder="e.g. ENG-PC-27 Lateral Movement"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs text-on-surface-muted mb-1 block">Description</label>
                <textarea
                  className="input-ghost w-full resize-none"
                  rows={3}
                  placeholder="Optional investigation description…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>

            {createError && (
              <p className="text-error text-xs mt-2">{createError}</p>
            )}

            <div className="flex gap-2 mt-4">
              <button
                onClick={handleCreate}
                disabled={!title.trim() || creating}
                className="btn-primary flex-1"
              >
                {creating ? 'Creating…' : 'Create Investigation'}
              </button>
              <button
                onClick={() => setModalOpen(false)}
                className="btn-ghost"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
