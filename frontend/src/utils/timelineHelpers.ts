import { format, parseISO } from 'date-fns';
import type { Severity } from '../types';

/** Format a UTC ISO-8601 string to "HH:mm:ss UTC" monospace label */
export function formatTimestamp(iso: string): string {
  try {
    return format(parseISO(iso), "HH:mm:ss 'UTC'");
  } catch {
    return iso;
  }
}

/** Format a UTC ISO-8601 string to a full "yyyy-MM-dd HH:mm:ss UTC" string */
export function formatFullTimestamp(iso: string): string {
  try {
    return format(parseISO(iso), "yyyy-MM-dd HH:mm:ss 'UTC'");
  } catch {
    return iso;
  }
}

export const formatUtc = formatFullTimestamp;

/** Format a UTC ISO-8601 string to a locale-friendly date string */
export function formatDate(iso: string): string {
  try {
    return format(parseISO(iso), 'MMM d, yyyy');
  } catch {
    return iso;
  }
}

/** Tailwind badge classes per event type */
export function eventTypeBadgeClass(eventType: string): string {
  const t = eventType.toLowerCase();
  if (t.includes('auth') || t.includes('login') || t.includes('logon'))
    return 'bg-primary/20 text-primary border border-primary/30';
  if (t.includes('process') || t.includes('exec'))
    return 'bg-secondary/20 text-secondary border border-secondary/30';
  if (t.includes('network') || t.includes('connect') || t.includes('dns'))
    return 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
  if (t.includes('file') || t.includes('access') || t.includes('read'))
    return 'bg-surface-highest text-on-surface-muted border border-outline-variant';
  return 'bg-surface-highest text-on-surface-muted border border-outline-variant';
}

/** Tailwind badge classes per severity */
export function severityBadgeClass(severity: Severity | null): string {
  switch (severity) {
    case 'critical':
      return 'bg-error-container text-error border border-error/30';
    case 'high':
      return 'bg-orange-900/40 text-orange-400 border border-orange-500/30';
    case 'medium':
      return 'bg-secondary/20 text-secondary border border-secondary/30';
    case 'low':
      return 'bg-surface-highest text-on-surface-muted border border-outline-variant';
    default:
      return 'bg-surface-highest text-on-surface-muted border border-outline-variant';
  }
}

/** Tailwind badge classes per investigation status */
export function statusBadgeClass(status: string): string {
  switch (status) {
    case 'OPEN':
      return 'bg-primary/20 text-primary border border-primary/30';
    case 'UNDER_REVIEW':
      return 'bg-secondary/20 text-secondary border border-secondary/30';
    case 'CLOSED':
      return 'bg-surface-highest text-on-surface-muted border border-outline-variant';
    default:
      return 'bg-surface-highest text-on-surface-muted border border-outline-variant';
  }
}

export function statusLabel(status: string): string {
  return status.replace('_', ' ');
}
