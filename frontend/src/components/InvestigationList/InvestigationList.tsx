import { useNavigate } from 'react-router-dom';
import type { Investigation, InvestigationStatus } from '../../types';
import {
  statusBadgeClass,
  statusLabel,
  severityBadgeClass,
  formatDate,
} from '../../utils/timelineHelpers';

interface Props {
  investigations: Investigation[];
  loading: boolean;
  error: string | null;
  onStatusFilter: (s: InvestigationStatus | undefined) => void;
}

const STATUS_FILTERS: Array<{ value: InvestigationStatus | undefined; label: string }> = [
  { value: undefined, label: 'All' },
  { value: 'OPEN', label: 'Open' },
  { value: 'UNDER_REVIEW', label: 'Under Review' },
  { value: 'CLOSED', label: 'Closed' },
];

export default function InvestigationList({ investigations, loading, error, onStatusFilter }: Props) {
  const navigate = useNavigate();

  const statusCount = (s: InvestigationStatus) => investigations.filter((i) => i.status === s).length;

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total', value: investigations.length, color: 'text-primary' },
          { label: 'Open', value: statusCount('OPEN'), color: 'text-primary' },
          { label: 'Under Review', value: statusCount('UNDER_REVIEW'), color: 'text-secondary' },
          { label: 'Closed', value: statusCount('CLOSED'), color: 'text-on-surface-muted' },
        ].map(({ label, value, color }) => (
          <div key={label} className="sentinel-card px-4 py-5">
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
            <p className="text-sm text-on-surface-muted mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={label}
            onClick={() => onStatusFilter(value)}
            className="badge-pill cursor-pointer hover:border-primary/40 transition-colors bg-surface-high text-on-surface-muted border border-outline-variant"
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="sentinel-card overflow-hidden">
        {loading && (
          <div className="p-8 text-center text-primary animate-pulse">Loading investigations…</div>
        )}
        {error && !loading && (
          <div className="p-6 text-error text-sm">{error}</div>
        )}
        {!loading && investigations.length === 0 && !error && (
          <div className="p-12 flex flex-col items-center gap-3">
            <span className="text-5xl opacity-20">🔍</span>
            <p className="text-on-surface-muted text-sm">No investigations yet. Create one to get started.</p>
          </div>
        )}
        {!loading && investigations.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-widest text-on-surface-muted border-b border-outline-variant/20">
                <th className="px-4 py-3 font-semibold">Title</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Created</th>
                <th className="px-4 py-3 font-semibold">Events</th>
                <th className="px-4 py-3 font-semibold">Outcome</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {investigations.map((inv, idx) => (
                <tr
                  key={inv.investigation_id}
                  className={`border-b border-outline-variant/10 hover:bg-surface-high transition-colors ${
                    idx % 2 === 0 ? 'bg-surface-container' : 'bg-surface-low'
                  }`}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-on-surface">{inv.title}</p>
                    {inv.description && (
                      <p className="text-xs text-on-surface-muted truncate max-w-xs">{inv.description}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge-pill ${statusBadgeClass(inv.status)}`}>
                      {statusLabel(inv.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 mono text-on-surface-muted">
                    {formatDate(inv.created_at)}
                  </td>
                  <td className="px-4 py-3 text-on-surface">{inv.event_count}</td>
                  <td className="px-4 py-3">
                    {inv.outcome ? (
                      <span className={`badge-pill ${severityBadgeClass(null)}`}>{inv.outcome}</span>
                    ) : (
                      <span className="text-on-surface-muted text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => navigate(`/investigations/${inv.investigation_id}`)}
                      className="btn-ghost text-xs py-1.5"
                    >
                      Open →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
