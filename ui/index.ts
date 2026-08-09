/**
 * The TypeScript half of civic-dashboard-kit: the canonical `DataStatus` union
 * and the provenance UI that renders it.
 *
 * Scope is deliberately narrow — see `docs/ARCHITECTURE.md` §7. Sections,
 * charts, narrative components, branding, and layout shell stay in each
 * dashboard; they are the ~85% that is domain-specific.
 *
 * Nothing exported here fetches anything. Every component takes
 * already-imported JSON as props, because each dashboard is a static export
 * (`output: 'export'`) whose frontend never queries a database or an API.
 */

export type { DataStatus } from './types';
export { resolveStatus } from './types';

export { default as SampleBadge } from './SampleBadge';
export { default as DataStatusPanel } from './DataStatusPanel';
export type { DataSource } from './DataStatusPanel';
