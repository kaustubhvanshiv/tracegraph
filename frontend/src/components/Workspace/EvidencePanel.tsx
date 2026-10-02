import { useState } from 'react';
import type { EvidenceDetail } from '../../types';
import { formatFullTimestamp, severityBadgeClass } from '../../utils/timelineHelpers';
import { ENTITY_COLORS } from '../../utils/cytoscapeConfig';

interface Props {
  evidence: EvidenceDetail | null;
  loading: boolean;
}

const KV_FIELDS: Array<{ key: keyof EvidenceDetail['event']; label: string }> = [
  { key: 'source_host', label: 'source_host' },
  { key: 'destination_host', label: 'destination_host' },
  { key: 'source_ip', label: 'source_ip' },
  { key: 'destination_ip', label: 'destination_ip' },
  { key: 'process', label: 'process' },
  { key: 'file', label: 'file' },
  { key: 'user', label: 'user' },
  { key: 'action', label: 'action' },
];

export default function EvidencePanel({ evidence, loading }: Props) {
  const [rawOpen, setRawOpen] = useState(false);

  if (loading) {
    return (
      <div className="sentinel-card h-full flex items-center justify-center">
        <span className="text-primary text-sm animate-pulse">Loading evidence…</span>
      </div>
    );
  }

  if (!evidence) {
    return (
      <div className="sentinel-card h-full flex flex-col items-center justify-center gap-2 p-6">
        <span className="text-4xl opacity-30">📋</span>
        <p className="text-on-surface-muted text-sm text-center">
          Select an event from the timeline or a node from the graph to inspect evidence.
        </p>
      </div>
    );
  }

  const ev = evidence.event;
  const copyId = () => navigator.clipboard.writeText(ev.event_id);

  return (
    <div className="sentinel-card flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant/20">
        <span className="text-sm font-semibold text-on-surface">Evidence</span>
        <button onClick={copyId} className="mono text-xs text-primary/80 hover:text-primary transition-colors">
          {ev.event_id} ⎘
        </button>
      </div>

      {/* Identity */}
      <div className="px-4 pt-4 pb-3 space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="badge-pill bg-primary/20 text-primary border border-primary/30">
            {ev.source_type}
          </span>
          {ev.severity && (
            <span className={`badge-pill ${severityBadgeClass(ev.severity)}`}>
              {ev.severity.toUpperCase()}
            </span>
          )}
          <span className="badge-pill bg-surface-highest text-on-surface-muted">{ev.event_type}</span>
        </div>
        <p className="mono text-on-surface-muted text-xs">{formatFullTimestamp(ev.timestamp)}</p>
      </div>

      {/* Normalized fields */}
      <div className="mx-4 mb-3 rounded-lg bg-surface-low p-3">
        <p className="text-[10px] uppercase tracking-widest text-on-surface-muted mb-2 font-semibold">
          Normalized Event
        </p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          {KV_FIELDS.map(({ key, label }) => {
            const val = ev[key] as string | null;
            if (!val) return null;
            return (
              <div key={label} className="col-span-1">
                <span className="text-[10px] text-on-surface-muted">{label}</span>
                <p className="mono text-xs text-on-surface break-all">{val}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Supported relationships */}
      {evidence.relationships.length > 0 && (
        <div className="mx-4 mb-3">
          <p className="text-[10px] uppercase tracking-widest text-on-surface-muted mb-2 font-semibold">
            Supports Relationship
          </p>
          {evidence.relationships.map((rel) => {
            const src = evidence.entities.find((e) => e.entity_id === rel.source_entity_id);
            const tgt = evidence.entities.find((e) => e.entity_id === rel.target_entity_id);
            return (
              <div
                key={rel.relationship_id}
                className="flex items-center gap-2 flex-wrap text-xs mb-2"
              >
                {src && (
                  <span
                    className="badge-pill text-white font-medium"
                    style={{ backgroundColor: ENTITY_COLORS[src.entity_type] + '33', color: ENTITY_COLORS[src.entity_type] }}
                  >
                    {src.entity_type}: {src.canonical_key}
                  </span>
                )}
                <span className="text-on-surface-muted">→</span>
                <span className="badge-pill bg-surface-highest text-on-surface font-mono">{rel.relationship_type}</span>
                <span className="text-on-surface-muted">→</span>
                {tgt && (
                  <span
                    className="badge-pill font-medium"
                    style={{ backgroundColor: ENTITY_COLORS[tgt.entity_type] + '33', color: ENTITY_COLORS[tgt.entity_type] }}
                  >
                    {tgt.entity_type}: {tgt.canonical_key}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Correlation signals */}
      {evidence.correlation_metadata.length > 0 && (
        <div className="mx-4 mb-3">
          <p className="text-[10px] uppercase tracking-widest text-on-surface-muted mb-1 font-semibold">
            Correlation Signals
          </p>
          <ul className="space-y-1">
            {evidence.correlation_metadata.map((m, i) => (
              <li key={i} className="text-xs text-on-surface-muted flex items-center gap-1.5">
                <span className="text-primary">·</span>
                {String(m.signal_name ?? m.explanation ?? JSON.stringify(m))}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Raw JSON */}
      <div className="mx-4 mb-4">
        <button
          onClick={() => setRawOpen((o) => !o)}
          className="flex items-center justify-between w-full bg-surface-lowest rounded-lg px-3 py-2 text-xs text-on-surface-muted hover:text-on-surface transition-colors"
        >
          <span className="font-semibold uppercase tracking-wider text-[10px]">Raw Event Data</span>
          <span>{rawOpen ? '▲' : '▼'}</span>
        </button>
        {rawOpen && (
          <pre className="bg-surface-lowest rounded-b-lg px-3 py-3 text-[11px] font-mono text-primary/90 overflow-x-auto border-t border-outline-variant/20 max-h-52 overflow-y-auto">
            {JSON.stringify(ev.raw_data ?? ev, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
