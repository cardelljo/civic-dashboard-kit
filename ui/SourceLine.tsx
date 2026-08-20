import type { ReactNode } from 'react';
import { ExternalLink } from 'lucide-react';

/**
 * The standard attribution line under a figure.
 *
 * Unlike `SampleBadge` and `DataStatusPanel`, this is not a lift of existing
 * code -- nothing shared existed to lift. The three dashboards each wrote this
 * line by hand, in three shapes, and 10 call sites turned out to be three
 * different *kinds* of thing wearing one `Source:` prefix: structured
 * attribution, attribution welded to a methodology caveat, and prose paragraphs
 * that merely began with the word. This component owns the first and gives the
 * caveat its own slot, so a caveat is a value rather than something baked into a
 * string literal.
 *
 * Rendered form is fixed on purpose -- a standard that each dashboard restyles
 * is not a standard:
 *
 *     Source: {source}↗ · {vintage} · {geography}   [caveat]
 *
 * `·` rather than commas so that an absent `vintage` or `geography` drops out
 * without leaving stray punctuation. The link wraps the source name, which is
 * the thing a reader clicks to verify a figure.
 */

/**
 * At least one of `source`/`vintage` is required, expressed as a union so
 * `<SourceLine />` with neither is a compile error. Note this does not protect
 * 901justice, which builds with `typescript.ignoreBuildErrors` -- hence the
 * runtime fallback below.
 */
type Attribution =
  | { source: string; vintage?: string }
  | { source?: string; vintage: string };

export type SourceLineProps = Attribution & {
  /** Where a reader verifies the figure. Wraps the source name when present. */
  sourceUrl?: string | null;
  /** Trailing geography or context, e.g. 'Memphis MSA', 'MSCS'. */
  geography?: string;
  /**
   * Methodology caveat -- suppression rules, COVID-disrupted years, what is and
   * is not machine-extracted. `ReactNode` because these routinely contain links.
   */
  caveat?: ReactNode;
  /**
   * Defaults to `data-note`, which all three dashboards define in `globals.css`
   * with their own muted color -- so the line inherits local theming rather than
   * importing a palette. Override for a different slot, e.g.
   * `section-subheader`.
   */
  className?: string;
};

export default function SourceLine({
  source,
  vintage,
  sourceUrl,
  geography,
  caveat,
  className = 'data-note',
}: SourceLineProps) {
  // The source name when there is one, otherwise the vintage stands in for it.
  // 901economy has no per-row publisher name today (its rows carry
  // `source_key: 'bea-gdp'` and the only human-readable name in `_meta` is its
  // own pipeline), so vintage-only is a supported shape, not a degenerate one.
  const primary = source ?? vintage;

  // Only a separate segment when it is not already serving as `primary`.
  const trailing = [source ? vintage : undefined, geography].filter(
    (segment): segment is string => Boolean(segment),
  );

  // Unreachable through the type above, reachable in a repo that ignores type
  // errors. Render the gap rather than hiding it: a figure whose provenance
  // silently vanished is the failure this whole contract exists to prevent.
  if (!primary) {
    return <p className={className}>Source: not recorded</p>;
  }

  return (
    <p className={className}>
      Source:{' '}
      {sourceUrl ? (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="underline inline-flex items-center gap-1"
        >
          {primary}
          <ExternalLink className="w-3 h-3" aria-hidden="true" />
        </a>
      ) : (
        primary
      )}
      {trailing.length > 0 ? ` · ${trailing.join(' · ')}` : ''}
      {caveat ? <> {caveat}</> : null}
    </p>
  );
}
