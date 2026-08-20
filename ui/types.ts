/**
 * The canonical `DataStatus` union.
 *
 * This is the whole reason the TypeScript half lives in this repo rather than
 * its own: these are the same status values `toolkit.snapshot.build_meta()`
 * writes and `validate_meta()` enforces on the Python side
 * (`src/toolkit/snapshot.py`). In separate repos the two would drift on
 * independent release cycles; here a change has to move both or neither.
 *
 * Meanings, so a consumer picks the same one the pipeline would:
 *
 * - `live`           — fetched from the source, no manual editing.
 * - `mixed`          — verified source data plus fields still needing
 *                      confirmation. Not "partly sample" — a `mixed` section
 *                      has no invented numbers in it.
 * - `sample`         — estimated/placeholder values. Must never reach a
 *                      published page unlabeled; that failure has happened.
 * - `gap`            — a documented public data gap. Renders as a gap naming
 *                      who holds the data, never as zero and never interpolated.
 * - `manual`         — a human transcribed the value from a source.
 * - `report-backed`  — extracted from a published report (PDF), reviewed by a
 *                      person before publication.
 *
 * `manual` and `report-backed` render identically today (both are
 * "not a live feed"); they are kept distinct because the provenance differs
 * and a consumer may want to tell them apart.
 */
export type DataStatus =
  | 'live'
  | 'mixed'
  | 'sample'
  | 'gap'
  | 'manual'
  | 'report-backed';

/**
 * Resolve the status of a snapshot that may predate the `status` field.
 *
 * The `_meta` contract carried only `isSample` before `status` existed, so
 * every consumer of an older snapshot needs the same fallback. Both components
 * here use this; export it so a dashboard's own components agree with them
 * rather than re-deriving the rule.
 */
export function resolveStatus(meta: {
  isSample: boolean;
  status?: DataStatus;
}): DataStatus {
  return meta.status ?? (meta.isSample ? 'sample' : 'live');
}
