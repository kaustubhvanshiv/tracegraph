import { useEffect, useState } from 'react';
import type { Investigation, InvestigationStatus, Note } from '../../types';
import { formatFullTimestamp, statusBadgeClass, statusLabel } from '../../utils/timelineHelpers';

interface Props {
  investigation: Investigation | null;
  notes?: Note[];
  onPatch?: (payload: { status?: InvestigationStatus; outcome?: string }) => Promise<void>;
  onAddNote?: (body: string) => Promise<void>;
  onInvestigationUpdated?: (inv: Investigation) => void;
}

const STATUSES: InvestigationStatus[] = ['OPEN', 'UNDER_REVIEW', 'CLOSED'];

const OUTCOMES = [
  { value: '', label: 'Select verdict…' },
  { value: 'TRUE_POSITIVE', label: 'True Positive' },
  { value: 'FALSE_POSITIVE', label: 'False Positive' },
  { value: 'INCONCLUSIVE', label: 'Inconclusive' },
  { value: 'ESCALATED', label: 'Escalated' },
];

export default function AnalystDecisionPanel({
  investigation,
  notes = [],
  onPatch,
  onAddNote,
}: Props) {
  const [pendingStatus, setPendingStatus] = useState<InvestigationStatus>('OPEN');
  const [pendingOutcome, setPendingOutcome] = useState<string>('');
  const [noteText, setNoteText] = useState('');
  const [saving, setSaving] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);

  useEffect(() => {
    if (investigation) {
      setPendingStatus(investigation.status);
      setPendingOutcome(investigation.outcome ?? '');
    }
  }, [investigation]);

  const saveChanges = async () => {
    if (!onPatch) return;
    setSaving(true);
    try {
      await onPatch({
        status: pendingStatus,
        outcome: pendingOutcome || undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  const submitNote = async () => {
    if (!noteText.trim() || !onAddNote) return;
    setSaving(true);
    try {
      await onAddNote(noteText.trim());
      setNoteText('');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="sentinel-card flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/20">
        <span className="text-sm font-semibold text-on-surface">Analyst Decision</span>
        <span className="text-on-surface-muted text-xs">(Human verdict — separate from AI output)</span>
      </div>

      {/* Status */}
      <div className="px-4 pt-4 pb-3">
        <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
          Investigation Status
        </p>
        <div className="flex gap-2">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setPendingStatus(s)}
              className={`badge-pill cursor-pointer transition-colors ${
                pendingStatus === s
                  ? statusBadgeClass(s)
                  : 'bg-surface-highest text-on-surface-muted border border-outline-variant hover:border-primary/30'
              }`}
            >
              {statusLabel(s)}
            </button>
          ))}
        </div>
      </div>

      {/* Outcome */}
      <div className="mx-4 mb-3 rounded-lg bg-surface-low p-3">
        <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
          Verdict / Outcome
        </p>
        <select
          value={pendingOutcome}
          onChange={(e) => setPendingOutcome(e.target.value)}
          className="input-ghost w-full"
        >
          {OUTCOMES.map((o) => (
            <option key={o.value} value={o.value} className="bg-surface-low text-on-surface">
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Notes */}
      <div className="px-4 mb-3">
        <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
          Analyst Notes
        </p>
        <textarea
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          rows={3}
          className="input-ghost w-full resize-none"
          placeholder="Add investigation notes, observations, next steps…"
        />
        <div className="flex justify-between items-center mt-1">
          <span className="text-[10px] text-on-surface-muted">{noteText.length} chars</span>
          <button
            onClick={submitNote}
            disabled={!noteText.trim() || saving}
            className="btn-ghost text-xs py-1"
          >
            Add Note
          </button>
        </div>
      </div>

      {/* Note history */}
      {notes && notes.length > 0 && (
        <div className="px-4 mb-3 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold">
            Note History
          </p>
          {notes.map((n) => (
            <div key={n.note_id} className="bg-surface-low rounded-lg p-3">
              <div className="flex justify-between mb-1">
                <span className="text-xs text-primary">{n.author_id}</span>
                <span className="mono text-[10px] text-on-surface-muted">{formatFullTimestamp(n.created_at)}</span>
              </div>
              <p className="text-xs text-on-surface leading-relaxed">{n.body}</p>
            </div>
          ))}
        </div>
      )}

      {/* Audit trail */}
      {investigation && (
        <div className="mx-4 mb-3">
          <button
            onClick={() => setAuditOpen((o) => !o)}
            className="flex items-center justify-between w-full bg-surface-low rounded-lg px-3 py-2 text-xs text-on-surface-muted hover:text-on-surface transition-colors"
          >
            <span className="font-semibold uppercase tracking-wider text-[10px]">Audit Trail</span>
            <span>{auditOpen ? '▲' : '▼'}</span>
          </button>
          {auditOpen && (
            <div className="bg-surface-low rounded-b-lg px-3 pb-3 space-y-1.5">
              <div className="flex items-center gap-2 text-xs text-on-surface-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                <span className="mono">{formatFullTimestamp(investigation.updated_at)}</span>
                <span>Status set to {statusLabel(investigation.status)}</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-on-surface-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-surface-highest shrink-0" />
                <span className="mono">{formatFullTimestamp(investigation.created_at)}</span>
                <span>Investigation created</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="px-4 pb-4 mt-auto flex gap-2">
        <button
          onClick={saveChanges}
          disabled={saving}
          className="btn-primary flex-1 text-sm"
        >
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
