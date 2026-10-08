import { useEffect, useState, useCallback } from 'react';
import { summaryApi } from '../../services/summaryApi';
import type { SummaryResult } from '../../types';

interface Props {
  investigationId: string;
  onEvidenceRefClick?: (eventId: string) => void;
}

export default function AISummaryPanel({
  investigationId,
  onEvidenceRefClick = () => {},
}: Props) {
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(
    async (forceRefresh = false) => {
      if (!investigationId) return;
      setLoading(true);
      setUnavailable(false);
      setError(null);

      try {
        const result = forceRefresh
          ? await summaryApi.generate(investigationId, true)
          : await summaryApi.get(investigationId);
        setSummary(result);
      } catch (e: unknown) {
        // HTTP 503 → graceful degradation
        const is503 = (e as { response?: { status?: number } })?.response?.status === 503;
        if (is503) {
          setUnavailable(true);
        } else {
          setError(e instanceof Error ? e.message : 'Failed to load summary');
        }
      } finally {
        setLoading(false);
      }
    },
    [investigationId]
  );

  useEffect(() => {
    fetchSummary(false);
  }, [fetchSummary]);

  return (
    <div className="sentinel-card flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant/20">
        <span className="text-sm font-semibold text-on-surface">AI Investigation Summary</span>
        <button
          onClick={() => fetchSummary(true)}
          disabled={loading}
          className="text-xs text-on-surface-muted hover:text-primary transition-colors disabled:opacity-50 focus-ring"
          title="Regenerate summary"
        >
          ↺
        </button>
      </div>

      {/* Unavailable graceful degradation */}
      {unavailable && (
        <div className="m-4 p-3 rounded-lg bg-surface-low border border-outline-variant/30 text-sm text-on-surface-muted">
          <p className="font-semibold text-secondary mb-1">⚠ AI Summary Unavailable</p>
          <p>The AI summary service is currently unreachable. Graph, Timeline, and Evidence panels remain fully functional.</p>
          <button
            onClick={() => fetchSummary(false)}
            className="mt-2 text-xs text-primary hover:underline focus-ring"
          >
            Try again
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex-1 flex items-center justify-center gap-2 text-primary text-sm min-h-[100px] loading-pulse">
          <span className="animate-spin">◌</span> Generating summary…
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="m-4 p-3 rounded-lg bg-error-container/30 border border-error/20 text-error text-sm">
          {error}
        </div>
      )}

      {/* Content */}
      {summary && !loading && !error && !unavailable && (
        <div className="flex-1 px-4 py-3 space-y-4">
          {/* Overview */}
          <section>
            <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-1">
              Overview
            </p>
            <p className="text-sm text-on-surface leading-relaxed">{summary.overview}</p>
          </section>

          {/* Sequence */}
          {summary.chronological_sequence && summary.chronological_sequence.length > 0 && (
            <section className="bg-surface-low rounded-lg p-3">
              <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
                Sequence
              </p>
              <ol className="space-y-1.5">
                {summary.chronological_sequence.map((step, i) => (
                  <li key={i} className="flex gap-2 text-xs text-on-surface">
                    <span className="shrink-0 text-primary font-mono">{i + 1}.</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* Key entities */}
          {summary.key_entities && summary.key_entities.length > 0 && (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
                Key Entities
              </p>
              <div className="flex flex-wrap gap-1.5">
                {summary.key_entities.map((e, i) => (
                  <span key={i} className="badge-pill bg-surface-highest text-on-surface-muted border border-outline-variant text-xs">
                    {e}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Evidence refs */}
          {summary.evidence_refs && summary.evidence_refs.length > 0 && (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
                Supporting Evidence
              </p>
              <div className="flex flex-wrap gap-1.5">
                {summary.evidence_refs.map((ref, i) => (
                  <button
                    key={i}
                    onClick={() => onEvidenceRefClick(ref)}
                    className="badge-pill mono text-xs bg-surface-low text-primary border border-primary/30 hover:bg-primary/10 transition-colors focus-ring"
                  >
                    #{ref.slice(0, 12)}
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* Uncertainty */}
          {summary.uncertainty && (
            <section className="bg-secondary/10 border border-secondary/20 rounded-lg p-3">
              <p className="text-[10px] uppercase tracking-widest text-secondary font-semibold mb-1">
                ⚠ Uncertainty
              </p>
              <p className="text-xs text-on-surface-muted leading-relaxed">{summary.uncertainty}</p>
            </section>
          )}

          {/* Next questions */}
          {summary.next_questions && summary.next_questions.length > 0 && (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
                Suggested Next Steps
              </p>
              <ul className="space-y-1">
                {summary.next_questions.map((q, i) => (
                  <li key={i} className="text-xs text-on-surface-muted flex gap-1.5">
                    <span className="text-primary">→</span>
                    {q}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {/* Footer CTA */}
      {summary && !loading && (
        <div className="px-4 pb-4">
          <button
            onClick={() => fetchSummary(true)}
            className="w-full btn-primary text-sm focus-ring"
          >
            Regenerate Summary
          </button>
        </div>
      )}
    </div>
  );
}
