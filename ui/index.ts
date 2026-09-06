/**
 * The TypeScript half of civic-dashboard-kit: the canonical `DataStatus` union,
 * the provenance UI that renders it, and the shared Civic Storyboard Engine.
 *
 * Scope follows docs/ARCHITECTURE.md §7 and docs/CIVIC_ENGAGEMENT_SUITE.md.
 * Nothing exported here fetches anything. Every component takes already-imported
 * JSON or config as props, maintaining static export compatibility.
 */

export { type DataStatus, resolveStatus } from './types';

export { default as SampleBadge } from './SampleBadge';
export { default as DataStatusPanel } from './DataStatusPanel';
export type { DataSource } from './DataStatusPanel';

export { default as SourceLine } from './SourceLine';
export type { SourceLineProps } from './SourceLine';

// Civic Storyboard & Scrollytelling Suite
export { default as StoryboardPresenter } from './storyboard/StoryboardPresenter';
export type { StoryboardPresenterProps } from './storyboard/StoryboardPresenter';

export { default as StoryboardModal } from './storyboard/StoryboardModal';
export type { StoryboardModalProps } from './storyboard/StoryboardModal';

export * from './storyboard/types';
export * from './storyboard';
