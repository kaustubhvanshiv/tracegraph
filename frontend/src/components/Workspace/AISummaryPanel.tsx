import { useEffect, useState } from 'react';
import { summaryApi } from '../../services/summaryApi';
import type { SummaryResult } from '../../types';

interface Props {
  investigationId: string;
  onEvidenceRefClick: (eventId: string) => void;
}

export default function AISummaryPanel({ investigationId, onEvidenceRefClick }: Props) {
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async (force = false) => {
    setLoading(true);
    setError(null);
    setUnavailable(false);
    try {
      const data = force
        ? await summaryApi.generate(investigationId, true)
        : await summaryApi.get(investigationId);
      if (data.error_flag) {
        setError(data.error_message ?? 'Summary generation failed.');
      } else {
        setSummary(data);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '';
      if (msg.includes('503') || msg.toLowerCase().includes('unavailable')) {
        setUnavailable(true);
      } else {
        setError(msg || 'Failed to load AI summary.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [investigationId]);

  return (
    <div className="sentinel-card-high flex flex-col h-full overflow-y-auto border border-primary/10">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-primary/10">
        <div className="flex items-center gap-2">
          <span className="badge-pill bg-gradient-to-r from-purple-600/30 to-primary/30 text-primary border border-primary/30">
            ✦ AI Generated
          </span>
          <span className="text-xs text-on-surface-muted">TraceAI</span>
        </div>
        <button
          onClick={() => fetchSummary(true)}
          disabled={loading}
          className="text-xs text-on-surface-muted hover:text-primary transition-colors disabled:opacity-50"
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
            className="mt-2 text-xs text-primary hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex-1 flex items-center justify-center gap-2 text-primary text-sm">
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
          {summary.chronological_sequence.length > 0 && (
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
          {summary.key_entities.length > 0 && (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
                Key Entities
              </p>
              <div className="flex flex-wrap gap-1.5">
                {summary.key_entities.map((e) => (
                  <span key={e} className="badge-pill bg-surface-highest text-on-surface-muted border border-outline-variant text-xs">
                    {e}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Evidence refs */}
          {summary.evidence_refs.length > 0 && (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-on-surface-muted font-semibold mb-2">
                Supporting Evidence
              </p>
              <div className="flex flex-wrap gap-1.5">
                {summary.evidence_refs.map((ref) => (
                  <button
                    key={ref}
                    onClick={() => onEvidenceRefClick(ref)}
                    className="badge-pill mono text-xs bg-surface-low text-primary border border-primary/30 hover:bg-primary/10 transition-colors"
                  >
                    #{ref.slice(0, 12)}
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* Uncertainty */}
          <section className="bg-secondary/10 border border-secondary/20 rounded-lg p-3">
            <p className="text-[10px] uppercase tracking-widest text-secondary font-semibold mb-1">
              ⚠ Uncertainty
            </p>
            <p className="text-xs text-on-surface-muted leading-relaxed">{summary.uncertainty}</p>
          </section>

          {/* Next questions */}
          {summary.next_questions.length > 0 && (
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
            className="w-full btn-primary text-sm"
          >
            Regenerate Summary
          </button>
        </div>
      )}
    </div>
  );
}
