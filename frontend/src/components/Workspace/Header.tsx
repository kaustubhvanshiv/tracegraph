import { useNavigate } from 'react-router-dom';
import type { Investigation } from '../../types';
import { statusBadgeClass, statusLabel } from '../../utils/timelineHelpers';

interface Props {
  investigation: Investigation | null;
  onGenerateSummary: () => void;
}

export default function WorkspaceHeader({ investigation, onGenerateSummary }: Props) {
  const navigate = useNavigate();

  return (
    <header className="bg-surface-low border-b border-outline-variant/20 px-4 md:px-6 py-3 flex items-center justify-between gap-4 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={() => navigate('/investigations')}
          className="text-on-surface-muted hover:text-primary text-sm transition-colors shrink-0 px-2 py-1.5 rounded touch-manipulation focus-ring"
          aria-label="Back to investigations"
        >
          ← Investigations
        </button>
        <span className="text-outline-variant hidden sm:inline">/</span>
        {investigation ? (
          <>
            <h1 className="text-base font-semibold text-on-surface truncate">{investigation.title}</h1>
            <span className={`badge-pill shrink-0 ${statusBadgeClass(investigation.status)}`}>
              {statusLabel(investigation.status)}
            </span>
            <span className="badge-pill bg-surface-highest text-on-surface-muted shrink-0">
              {investigation.event_count} events
            </span>
          </>
        ) : (
          <span className="text-on-surface-muted text-sm">Loading…</span>
        )}
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <span className="mono text-[11px] text-on-surface-muted hidden md:block">
          Investigation Workspace
        </span>
        <button
          onClick={onGenerateSummary}
          className="btn-primary text-sm flex items-center gap-1.5 touch-manipulation focus-ring"
        >
          ✦ Generate Summary
        </button>
      </div>
    </header>
  );
}
