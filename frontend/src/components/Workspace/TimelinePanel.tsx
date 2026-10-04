import { useState, useEffect } from 'react';
import type { TimelineResult, TimelineEvent } from '../../types';
import {
  formatTimestamp,
  eventTypeBadgeClass,
  severityBadgeClass,
} from '../../utils/timelineHelpers';

interface Props {
  timeline?: TimelineResult | null;
  loading?: boolean;
  error?: string | null;
  selectedEventId?: string | null;
  highlightedEntityId?: string | null;
  selectedEntityId?: string | null;
  onEventSelected?: (eventId: string | null, entityIds: string[]) => void;
  onEventSelect?: (event: TimelineEvent) => void;
  onFilterChange?: (params: { event_type?: string; entity_id?: string }) => void;
  investigationId?: string;
}

const EVENT_TYPE_FILTERS = ['All', 'Auth', 'Process', 'Network', 'File'];

export default function TimelinePanel({
  timeline,
  loading = false,
  error = null,
  selectedEventId,
  highlightedEntityId,
  selectedEntityId,
  onEventSelected,
  onEventSelect,
  onFilterChange,
}: Props) {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');

  const activeHighlightedEntityId = highlightedEntityId || selectedEntityId || null;

  const events = timeline?.events ?? [];

  const filtered = events.filter((te) => {
    const ev = te.event;
    const matchType =
      typeFilter === 'All' ||
      ev.event_type.toLowerCase().includes(typeFilter.toLowerCase());
    const matchSearch =
      !search ||
      ev.event_id.toLowerCase().includes(search.toLowerCase()) ||
      (ev.source_host ?? '').toLowerCase().includes(search.toLowerCase()) ||
      (ev.user ?? '').toLowerCase().includes(search.toLowerCase()) ||
      ev.action.toLowerCase().includes(search.toLowerCase());
    return matchType && matchSearch;
  });

  // notify parent when typeFilter changes
  useEffect(() => {
    if (typeFilter !== 'All') {
      onFilterChange?.({ event_type: typeFilter.toLowerCase() });
    }
  }, [typeFilter]);

  const isRowHighlighted = (te: TimelineEvent) =>
    activeHighlightedEntityId
      ? te.entity_ids.includes(activeHighlightedEntityId)
      : false;

  const handleRowClick = (te: TimelineEvent) => {
    if (onEventSelected) {
      onEventSelected(te.event.event_id, te.entity_ids);
    }
    if (onEventSelect) {
      onEventSelect(te);
    }
  };

  return (
    <div className="sentinel-card flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-outline-variant/20 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-on-surface">Event Timeline</span>
            <span className="badge-pill bg-surface-highest text-on-surface-muted mono">
              {timeline?.total ?? 0} events
            </span>
          </div>
        </div>
        {/* Search + filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <input
            className="input-ghost flex-1 min-w-[140px]"
            placeholder="Filter events…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="flex gap-1">
            {EVENT_TYPE_FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setTypeFilter(f)}
                className={`badge-pill text-xs cursor-pointer transition-colors ${
                  typeFilter === f
                    ? 'bg-primary/20 text-primary border border-primary/40'
                    : 'bg-surface-highest text-on-surface-muted border border-outline-variant hover:border-primary/30'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center h-20 text-primary text-sm gap-2">
            <span className="animate-spin">◌</span> Loading…
          </div>
        )}
        {error && !loading && (
          <div className="p-4 text-error text-sm">{error}</div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="p-6 text-center text-on-surface-muted text-sm">No events match the current filter.</div>
        )}
        {filtered.map((te, idx) => {
          const ev = te.event;
          const isSelected = ev.event_id === selectedEventId;
          const isHighlighted = isRowHighlighted(te);
          return (
            <button
              key={ev.event_id}
              onClick={() => handleRowClick(te)}
              className={`w-full text-left flex items-start gap-3 px-4 py-3 relative transition-colors cursor-pointer
                ${isSelected ? 'bg-surface-high' : idx % 2 === 0 ? 'bg-surface-container' : 'bg-surface-low'}
                ${isHighlighted && !isSelected ? 'ring-1 ring-inset ring-primary/30' : ''}
                hover:bg-surface-high`}
            >
              {/* Left accent */}
              <span
                className={`absolute left-0 top-0 bottom-0 w-[3px] rounded-r ${
                  isSelected ? 'bg-primary' : 'bg-transparent'
                }`}
              />
              {/* Timestamp */}
              <span className="mono text-on-surface-muted shrink-0 pt-0.5">
                {formatTimestamp(ev.timestamp)}
              </span>
              {/* Type badge */}
              <span className={`badge-pill shrink-0 ${eventTypeBadgeClass(ev.event_type)}`}>
                {ev.event_type.toUpperCase().slice(0, 7)}
              </span>
              {/* Content */}
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-on-surface block truncate">
                  {ev.source_host ?? ev.user ?? ev.event_id}
                </span>
                <span className="text-xs text-on-surface-muted truncate block">{ev.action}</span>
              </div>
              {/* Severity + ID */}
              <div className="flex flex-col items-end gap-1 shrink-0">
                {ev.severity && (
                  <span className={`badge-pill text-[10px] ${severityBadgeClass(ev.severity)}`}>
                    {ev.severity.toUpperCase()}
                  </span>
                )}
                <span className="mono text-on-surface-muted text-[10px]">
                  {ev.event_id.slice(0, 12)}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Footer */}
      {timeline && (
        <div className="px-4 py-2 border-t border-outline-variant/20 flex items-center justify-between">
          <span className="mono text-on-surface-muted text-[11px]">
            Showing {filtered.length} of {timeline.total}
          </span>
        </div>
      )}
    </div>
  );
}
