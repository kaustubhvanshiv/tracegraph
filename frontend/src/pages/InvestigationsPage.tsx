import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInvestigationList } from '../hooks/useInvestigation';
import InvestigationList from '../components/InvestigationList/InvestigationList';
import { tokenStore } from '../services/authApi';
import type { InvestigationStatus } from '../types';

/** Derive two-letter initials from a username string */
function getInitials(username: string): string {
  const parts = username.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return username.slice(0, 2).toUpperCase();
}

export default function InvestigationsPage() {
  const navigate = useNavigate();
  const { investigations, loading, error, fetch, create } = useInvestigationList();
  const [statusFilter, setStatusFilter] = useState<InvestigationStatus | undefined>(undefined);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalExiting, setModalExiting] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [avatarOpen, setAvatarOpen] = useState(false);

  const username = tokenStore.getUser() ?? 'analyst';
  const initials = getInitials(username);

  useEffect(() => { fetch(); }, [fetch]);

  // Close avatar dropdown on outside click
  useEffect(() => {
    if (!avatarOpen) return;
    const close = () => setAvatarOpen(false);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [avatarOpen]);

  const filtered = statusFilter
    ? investigations.filter((i) => i.status === statusFilter)
    : investigations;

  const handleCreate = async () => {
    if (!title.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const inv = await create({ title: title.trim(), description: description.trim() || undefined });
      setModalExiting(true);
      setTimeout(() => {
        setModalOpen(false);
        setModalExiting(false);
        setTitle('');
        setDescription('');
        navigate(`/investigations/${inv.investigation_id}`);
      }, 100);
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create investigation');
    } finally {
      setCreating(false);
    }
  };

  const handleCancel = () => {
    setModalExiting(true);
    setTimeout(() => {
      setModalOpen(false);
      setModalExiting(false);
      setTitle('');
      setDescription('');
      setCreateError(null);
    }, 100);
  };

  return (
    <div className="min-h-screen bg-surface">

      {/* ── Top Navigation ─────────────────────────────────────────────── */}
      <header className="bg-surface-low px-4 md:px-8 py-0 flex items-center justify-between h-16 sticky top-0 z-30">

        {/* Left — wordmark */}
        <div className="flex items-center gap-2.5">
          {/* Radar node icon */}
          <svg className="w-5 h-5 text-primary shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" />
            <circle cx="12" cy="12" r="7" strokeOpacity={0.4} />
            <circle cx="12" cy="12" r="11" strokeOpacity={0.15} />
            <line x1="12" y1="12" x2="19" y2="5" strokeWidth={1.5} />
          </svg>
          <span className="text-base font-bold text-on-surface tracking-tight">TraceGraph</span>
          <span className="hidden sm:block text-on-surface-muted text-xs font-mono ml-1 opacity-40">Sentinel Hub</span>
        </div>

        {/* Center — live sync indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-container">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-50" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
          </span>
          <span className="text-xs font-mono text-primary tracking-wide">Live Pipeline Sync Active</span>
        </div>

        {/* Right — actions + user */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setModalOpen(true)}
            className="btn-primary flex items-center gap-1.5 text-sm touch-manipulation focus-ring"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            <span className="hidden sm:inline">New Investigation</span>
            <span className="sm:hidden">New</span>
          </button>

          {/* Avatar dropdown */}
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setAvatarOpen((v) => !v); }}
              className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-full hover:bg-surface-container transition-colors focus-ring touch-manipulation"
              aria-label="User menu"
            >
              <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center text-xs font-bold text-on-primary select-none">
                {initials}
              </div>
              <span className="hidden md:block text-xs text-on-surface-muted font-mono truncate max-w-[120px]">{username}</span>
              <svg className={`w-3 h-3 text-on-surface-muted transition-transform ${avatarOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {avatarOpen && (
              <div className="absolute right-0 top-full mt-2 w-48 bg-surface-highest rounded-xl shadow-sentinel-md border border-outline-variant/20 overflow-hidden z-50">
                <div className="px-3 py-3 border-b border-outline-variant/10">
                  <p className="text-xs font-semibold text-on-surface truncate">{username}</p>
                  <p className="text-[10px] text-on-surface-muted font-mono mt-0.5">Tier 3 SOC Analyst</p>
                </div>
                <button
                  onClick={() => { tokenStore.clear(); navigate('/login', { replace: true }); }}
                  className="w-full text-left px-3 py-2.5 text-sm text-error hover:bg-surface-high transition-colors flex items-center gap-2"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── Page content ───────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 md:px-8 py-6 md:py-8">

        {/* Page heading */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-on-surface tracking-tight">SOC Workspace</h1>
          <p className="text-on-surface-muted text-sm mt-1">
            Track and manage security investigations across endpoints, identity clusters, and cloud environments.
          </p>
        </div>

        <InvestigationList
          investigations={filtered}
          loading={loading}
          error={error}
          onStatusFilter={setStatusFilter}
        />
      </main>

      {/* ── Create Investigation Modal ──────────────────────────────────── */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-surface/80 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          onClick={(e) => { if (e.target === e.currentTarget) handleCancel(); }}
        >
          <div className={`bg-surface-highest rounded-2xl w-full max-w-md shadow-sentinel-md ${modalExiting ? 'modal-exit' : 'modal-enter'}`}>

            {/* Modal header */}
            <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-outline-variant/10">
              <div>
                <h2 id="modal-title" className="text-base font-semibold text-on-surface">New Investigation</h2>
                <p className="text-xs text-on-surface-muted mt-0.5">Opens a new workspace when created.</p>
              </div>
              <button
                onClick={handleCancel}
                className="w-7 h-7 rounded-full flex items-center justify-center text-on-surface-muted hover:bg-surface-high hover:text-on-surface transition-colors focus-ring"
                aria-label="Close"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal body */}
            <div className="px-6 py-5 space-y-4">
              <div>
                <label htmlFor="inv-title" className="block text-[10px] text-on-surface-muted uppercase tracking-widest font-mono mb-1.5">
                  Title <span className="text-error">*</span>
                </label>
                <input
                  id="inv-title"
                  className="input-ghost w-full focus-ring"
                  placeholder="e.g. APT29 Lateral Movement — Corp DC"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleCreate()}
                  autoFocus
                />
              </div>
              <div>
                <label htmlFor="inv-desc" className="block text-[10px] text-on-surface-muted uppercase tracking-widest font-mono mb-1.5">
                  Description
                </label>
                <textarea
                  id="inv-desc"
                  className="input-ghost w-full resize-none focus-ring"
                  rows={3}
                  placeholder="Optional — affected hosts, TTPs, initial indicators…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              {createError && (
                <div className="flex items-center gap-2 text-error text-xs bg-error-container/20 rounded-lg px-3 py-2">
                  <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                  </svg>
                  {createError}
                </div>
              )}
            </div>

            {/* Modal footer */}
            <div className="px-6 pb-5 flex gap-2">
              <button
                onClick={handleCreate}
                disabled={!title.trim() || creating}
                className="btn-primary flex-1 flex items-center justify-center gap-2 touch-manipulation focus-ring disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creating ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-on-primary/30 border-t-on-primary rounded-full animate-spin" />
                    Creating…
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                    </svg>
                    Create Investigation
                  </>
                )}
              </button>
              <button
                onClick={handleCancel}
                className="btn-ghost touch-manipulation focus-ring"
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
