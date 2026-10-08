import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Investigation, InvestigationStatus } from '../../types';
import { formatDate, statusBadgeClass, statusLabel } from '../../utils/timelineHelpers';

interface Props {
  investigations: Investigation[];
  loading: boolean;
  error?: string | null;
  onStatusFilter?: (status?: InvestigationStatus) => void;
}

const STATUS_FILTERS: Array<{ value?: InvestigationStatus; label: string }> = [
  { value: undefined, label: 'All' },
  { value: 'OPEN', label: 'Open' },
  { value: 'UNDER_REVIEW', label: 'Under Review' },
  { value: 'CLOSED', label: 'Closed' },
];

const OUTCOME_LABELS: Record<string, string> = {
  TRUE_POSITIVE: 'True Positive',
  FALSE_POSITIVE: 'False Positive',
  INCONCLUSIVE: 'Inconclusive',
  ESCALATED: 'Escalated',
};

function outcomeBadgeClass(outcome: string): string {
  switch (outcome) {
    case 'TRUE_POSITIVE':
      return 'bg-error-container text-error border border-error/30';
    case 'FALSE_POSITIVE':
      return 'bg-primary-container/20 text-primary border border-primary/30';
    case 'ESCALATED':
      return 'bg-tertiary-container/20 text-tertiary border border-tertiary/30';
    case 'INCONCLUSIVE':
    default:
      return 'bg-surface-highest text-on-surface-muted border border-outline-variant';
  }
}

/** Shorten an investigation UUID to a display ID like TG-8902 */
function shortId(id: string): string {
  // Use last 4 hex chars as a numeric-ish suffix
  const suffix = parseInt(id.replace(/-/g, '').slice(-4), 16) % 10000;
  return `TG-${suffix.toString().padStart(4, '0')}`;
}

const PAGE_SIZE = 15;

export default function InvestigationList({ investigations, loading, error, onStatusFilter }: Props) {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState<InvestigationStatus | undefined>(undefined);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const statusCount = (s?: InvestigationStatus) =>
    s ? investigations.filter((i) => i.status === s).length : investigations.length;

  const filtered = useMemo(() => {
    let list = activeFilter ? investigations.filter((i) => i.status === activeFilter) : investigations;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          i.description?.toLowerCase().includes(q) ||
          shortId(i.investigation_id).toLowerCase().includes(q)
      );
    }
    return list;
  }, [investigations, activeFilter, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function handleFilterChange(value?: InvestigationStatus) {
    setActiveFilter(value);
    setPage(1);
    onStatusFilter?.(value);
  }

  function handleSearch(q: string) {
    setSearch(q);
    setPage(1);
  }

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total', value: statusCount(), color: 'text-on-surface' },
          { label: 'Open', value: statusCount('OPEN'), color: 'text-primary' },
          { label: 'Under Review', value: statusCount('UNDER_REVIEW'), color: 'text-secondary' },
          { label: 'Closed', value: statusCount('CLOSED'), color: 'text-on-surface-muted' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-surface-container rounded-xl px-4 py-5">
            <p className={`text-3xl font-bold tabular-nums ${color}`}>{value}</p>
            <p className="text-xs text-on-surface-muted mt-1 uppercase tracking-widest font-mono">{label}</p>
          </div>
        ))}
      </div>

      {/* Search + filter bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        {/* Search */}
        <div className="relative flex-1 min-w-0">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-on-surface-muted pointer-events-none"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search by title, ID, or description…"
            className="w-full pl-9 pr-3 py-2 rounded-md text-sm bg-surface-low border-0 text-on-surface placeholder-on-surface-muted focus:outline-none focus:ring-1 focus:ring-primary/40 transition"
          />
        </div>

        {/* Status filter pills */}
        <div className="flex gap-1.5 flex-wrap shrink-0">
          {STATUS_FILTERS.map(({ value, label }) => {
            const isActive = activeFilter === value;
            return (
              <button
                key={label}
                onClick={() => handleFilterChange(value)}
                className={`badge-pill cursor-pointer transition-all text-xs font-medium touch-manipulation focus-ring ${
                  isActive
                    ? 'bg-primary-container text-on-primary border border-transparent shadow-sm'
                    : 'bg-surface-high text-on-surface-muted border border-outline-variant hover:border-primary/40 hover:text-on-surface'
                }`}
              >
                {label}
                <span className={`ml-1 tabular-nums ${isActive ? 'opacity-80' : 'opacity-50'}`}>
                  {statusCount(value)}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Table card */}
      <div className="bg-surface-container rounded-xl overflow-hidden">
        {loading && (
          <div className="p-10 flex flex-col items-center gap-3">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            <p className="text-on-surface-muted text-sm font-mono">Loading investigations…</p>
          </div>
        )}

        {error && !loading && (
          <div className="p-6 flex items-center gap-2 text-error text-sm">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            </svg>
            {error}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="p-16 flex flex-col items-center gap-4 text-center">
            <div className="w-16 h-16 rounded-full bg-surface-high flex items-center justify-center">
              <svg className="w-8 h-8 text-on-surface-muted opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <div>
              <p className="text-on-surface font-medium">
                {search ? 'No investigations match your search' : 'No active incidents found'}
              </p>
              <p className="text-on-surface-muted text-sm mt-1">
                {search
                  ? 'Try adjusting your search terms or clearing filters.'
                  : 'All telemetry queues are clear. Create a new investigation to get started.'}
              </p>
            </div>
          </div>
        )}

        {!loading && !error && paginated.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-widest text-on-surface-muted bg-surface-high/60">
                    <th className="px-4 py-3 font-semibold">Investigation</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Outcome</th>
                    <th className="px-4 py-3 font-semibold">Created</th>
                    <th className="px-4 py-3 font-semibold text-right">Events</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((inv) => (
                    <tr
                      key={inv.investigation_id}
                      onClick={() => navigate(`/investigations/${inv.investigation_id}`)}
                      className="border-t border-outline-variant/10 hover:bg-surface-high/60 transition-colors cursor-pointer group"
                    >
                      {/* Title + ID */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-start gap-2.5">
                          <span className="font-mono text-[10px] text-on-surface-muted bg-surface-highest px-1.5 py-0.5 rounded mt-0.5 shrink-0 border border-outline-variant/30">
                            {shortId(inv.investigation_id)}
                          </span>
                          <div className="min-w-0">
                            <p className="font-medium text-on-surface group-hover:text-primary transition-colors truncate">
                              {inv.title}
                            </p>
                            {inv.description && (
                              <p className="text-xs text-on-surface-muted truncate max-w-xs mt-0.5">
                                {inv.description}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5 whitespace-nowrap">
                        <span className={`badge-pill ${statusBadgeClass(inv.status)}`}>
                          <span className={`w-1.5 h-1.5 rounded-full inline-block ${
                            inv.status === 'OPEN' ? 'bg-primary animate-pulse' :
                            inv.status === 'UNDER_REVIEW' ? 'bg-secondary' : 'bg-on-surface-muted'
                          }`} />
                          {statusLabel(inv.status)}
                        </span>
                      </td>

                      {/* Outcome */}
                      <td className="px-4 py-3.5 whitespace-nowrap">
                        {inv.outcome ? (
                          <span className={`badge-pill ${outcomeBadgeClass(inv.outcome)}`}>
                            {OUTCOME_LABELS[inv.outcome] ?? inv.outcome}
                          </span>
                        ) : (
                          <span className="text-on-surface-muted text-xs font-mono">—</span>
                        )}
                      </td>

                      {/* Created */}
                      <td className="px-4 py-3.5 font-mono text-xs text-on-surface-muted whitespace-nowrap">
                        {formatDate(inv.created_at)}
                      </td>

                      {/* Event count */}
                      <td className="px-4 py-3.5 font-mono text-xs text-on-surface text-right whitespace-nowrap">
                        {(inv.event_count ?? 0).toLocaleString()}
                      </td>

                      {/* Action */}
                      <td className="px-4 py-3.5 text-right whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-on-surface-muted group-hover:text-primary transition-colors">
                          Open
                          <svg className="w-3.5 h-3.5 -translate-x-0.5 group-hover:translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                          </svg>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination footer */}
            <div className="px-4 py-3 border-t border-outline-variant/10 flex items-center justify-between bg-surface-high/30">
              <p className="text-xs text-on-surface-muted font-mono">
                Showing{' '}
                <span className="text-on-surface">
                  {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)}
                </span>{' '}
                of{' '}
                <span className="text-on-surface">{filtered.length}</span>{' '}
                investigations
              </p>
              {totalPages > 1 && (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-2.5 py-1 rounded text-xs text-on-surface-muted border border-outline-variant/30 hover:border-primary/40 hover:text-on-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    ‹
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                    .reduce<Array<number | '…'>>((acc, p, idx, arr) => {
                      if (idx > 0 && (arr[idx - 1] as number) + 1 < p) acc.push('…');
                      acc.push(p);
                      return acc;
                    }, [])
                    .map((p, i) =>
                      p === '…' ? (
                        <span key={`ellipsis-${i}`} className="px-2 py-1 text-xs text-on-surface-muted">…</span>
                      ) : (
                        <button
                          key={p}
                          onClick={() => setPage(p as number)}
                          className={`px-2.5 py-1 rounded text-xs transition-colors ${
                            page === p
                              ? 'bg-primary-container text-on-primary font-semibold border border-transparent'
                              : 'text-on-surface-muted border border-outline-variant/30 hover:border-primary/40 hover:text-on-surface'
                          }`}
                        >
                          {p}
                        </button>
                      )
                    )}
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-2.5 py-1 rounded text-xs text-on-surface-muted border border-outline-variant/30 hover:border-primary/40 hover:text-on-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    ›
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
