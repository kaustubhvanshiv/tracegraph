import { parseISO } from 'date-fns';

/**
 * Format an ISO string to a UTC time string.
 * Example: 2024-01-01T15:30:00Z -> '2024-01-01 15:30:00 UTC'
 */
export const formatUtc = (isoString: string): string => {
  try {
    const date = parseISO(isoString);
    // Since we're rendering, we'll format it assuming local timezone but append UTC if backend sends Z.
    // For a strict UTC display, date-fns 'format' uses local tz unless using date-fns-tz. 
    // To keep it simple, we format and append 'Z' or use standard ISO format
    // A quick hack for strict UTC string without extra deps:
    return date.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  } catch {
    return isoString;
  }
};
