/**
 * Officeholder terms as neutral context markers on a trend chart: a dotted
 * line where the officeholder changes and the name above each term. No
 * judgment colors, no party shading, no labels beyond the name.
 *
 * Jurisdiction-neutral, like `GeographyTag`: the kit holds the shape and the
 * placement arithmetic; each dashboard holds its own terms, keyed by its own
 * geography ids (e.g. `{ 'memphis-city': { office: 'Mayor', terms: [...] } }`).
 * Drawing stays in the dashboard's chart library (docs/ARCHITECTURE.md §7.2
 * holds shared charts out until three dashboards use one).
 */

export type OfficeTerm = {
  /** Name as printed on the chart, e.g. a surname. */
  name: string;
  /** First day in office, YYYY-MM-DD. */
  start: string;
  /** Last day in office, YYYY-MM-DD; null or omitted while in office. */
  end?: string | null;
  /** Interim or acting officeholder. Hidden unless `includeActing`. */
  acting?: boolean;
  /** Where the dates were checked. */
  source?: string;
};

export type OfficeholderSeries = {
  /** Office name for the legend or info note, e.g. "Mayor". */
  office: string;
  terms: OfficeTerm[];
};

/** Officeholder series keyed by a dashboard's own geography ids. */
export type OfficeholderConfig = Record<string, OfficeholderSeries>;

export type TermMarker = {
  name: string;
  /** Decimal year where the term starts inside the range (clipped to `from`). */
  start: number;
  /** Decimal year where the term ends inside the range (clipped to `to`). */
  end: number;
  /** True when the term began before `from`; draw no line at `start`. */
  startsBeforeRange: boolean;
  /** Midpoint of the visible span, for the name label. */
  labelAt: number;
};

export type TermMarkerOptions = {
  /** Range of the chart's x axis, in decimal years. */
  from: number;
  to: number;
  /** Include acting/interim terms. Default false. */
  includeActing?: boolean;
  /** Hide terms shorter than this many days (after clipping). Default 180. */
  minDays?: number;
  /** "Today" for open terms, YYYY-MM-DD. Default: the range end. */
  asOf?: string;
};

/** `2016-01-01` -> 2016.0; `2009-10-30` -> ~2009.83. Rejects malformed dates. */
export function decimalYear(date: string): number {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) throw new Error(`Expected YYYY-MM-DD, got "${date}"`);
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const at = Date.UTC(y, m - 1, d);
  const check = new Date(at);
  if (check.getUTCMonth() !== m - 1 || check.getUTCDate() !== d) {
    throw new Error(`Not a calendar date: "${date}"`);
  }
  const yearStart = Date.UTC(y, 0, 1);
  const yearLength = Date.UTC(y + 1, 0, 1) - yearStart;
  return y + (at - yearStart) / yearLength;
}

/**
 * The terms visible in `[from, to]`, in start order, clipped to the range.
 * Short terms (under `minDays` visible) and acting terms are dropped by
 * default so a few-month interim doesn't crowd the labels; the caller says so
 * in its info note if it matters.
 */
export function termMarkers(series: OfficeholderSeries | undefined, options: TermMarkerOptions): TermMarker[] {
  if (!series) return [];
  const { from, to, includeActing = false, minDays = 180 } = options;
  if (!(to > from)) return [];
  const openEnd = options.asOf ? decimalYear(options.asOf) : to;
  return series.terms
    .filter(t => includeActing || !t.acting)
    .map(t => ({ t, start: decimalYear(t.start), end: t.end ? decimalYear(t.end) : openEnd }))
    .filter(({ start, end }) => end > from && start < to)
    .sort((a, b) => a.start - b.start)
    .map(({ t, start, end }) => {
      const s = Math.max(start, from);
      const e = Math.min(end, to);
      return { name: t.name, start: s, end: e, startsBeforeRange: start < from, labelAt: (s + e) / 2 };
    })
    .filter(m => (m.end - m.start) * 365.25 >= minDays - 1e-9);
}
