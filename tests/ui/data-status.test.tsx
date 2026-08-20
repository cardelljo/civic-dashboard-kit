import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  DataStatusPanel,
  SampleBadge,
  resolveStatus,
  type DataSource,
  type DataStatus,
} from '../../ui';

/**
 * These assert the behavior a dashboard depends on, not the markup: which
 * statuses produce a badge, that `live` produces none, and that the panel's
 * counts and detail rows come out of the props it was given.
 *
 * Deliberately not asserted: Tailwind class names. The components carry utility
 * classes that only resolve if the consuming app's `tailwind.config` scans this
 * package (see README, "Adopting the TypeScript half"). That is a consumer
 * configuration failure, and it cannot be caught here -- there is no Tailwind
 * build in this repo. It shows up as unstyled output in the consuming app.
 */

function source(overrides: Partial<DataSource> = {}): DataSource {
  return {
    id: 'acs-median-income',
    label: 'Census ACS median household income',
    section: 'People',
    isSample: false,
    lastFetched: '2026-08-01T00:00:00',
    fetchedBy: 'fetch_acs.py',
    notes: '',
    ...overrides,
  };
}

describe('resolveStatus', () => {
  it('prefers an explicit status over the isSample fallback', () => {
    expect(resolveStatus({ isSample: true, status: 'live' })).toBe('live');
    expect(resolveStatus({ isSample: false, status: 'gap' })).toBe('gap');
  });

  it('falls back to isSample when status is absent', () => {
    expect(resolveStatus({ isSample: true })).toBe('sample');
    expect(resolveStatus({ isSample: false })).toBe('live');
  });
});

describe('SampleBadge', () => {
  it('renders nothing for live data', () => {
    const { container } = render(<SampleBadge isSample={false} status="live" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders nothing when isSample is false and status is absent', () => {
    const { container } = render(<SampleBadge isSample={false} />);
    expect(container.innerHTML).toBe('');
  });

  const labels: [DataStatus | undefined, boolean, string][] = [
    ['sample', false, 'Sample Data'],
    [undefined, true, 'Sample Data'],
    ['mixed', false, 'Mixed Sources'],
    ['gap', false, 'Data Gap'],
    ['manual', false, 'Report-Backed'],
    ['report-backed', false, 'Report-Backed'],
  ];

  it.each(labels)('labels status=%s isSample=%s as "%s"', (status, isSample, label) => {
    render(<SampleBadge isSample={isSample} status={status} />);
    expect(screen.getByText(label)).toBeDefined();
  });
});

describe('DataStatusPanel', () => {
  const sources = [
    source({ id: 'a', label: 'Live source', status: 'live' }),
    source({ id: 'b', label: 'Second live source', status: 'live' }),
    source({ id: 'c', label: 'Gap source', status: 'gap' }),
    source({ id: 'd', label: 'Sample source', isSample: true, status: undefined }),
  ];

  it('summarizes counts by resolved status', () => {
    render(<DataStatusPanel sources={sources} />);
    expect(screen.getByText('2 live')).toBeDefined();
    expect(screen.getByText('1 gaps')).toBeDefined();
    expect(screen.getByText('1 sample')).toBeDefined();
  });

  it('omits a count for a status no source has', () => {
    render(<DataStatusPanel sources={sources} />);
    expect(screen.queryByText(/mixed$/)).toBeNull();
    expect(screen.queryByText(/report$/)).toBeNull();
  });

  it('starts collapsed, so a source label is not in the document', () => {
    render(<DataStatusPanel sources={sources} />);
    expect(screen.getByText('Show details')).toBeDefined();
    expect(screen.queryByText('Live source')).toBeNull();
  });

  it('reveals every source label once expanded', () => {
    render(<DataStatusPanel sources={sources} />);
    fireEvent.click(screen.getByText('Data Sources Status'));
    for (const src of sources) {
      expect(screen.getByText(src.label)).toBeDefined();
    }
  });

  it('shows the fetch timestamp for a live source and a gap note for a gap', () => {
    render(<DataStatusPanel sources={sources} />);
    fireEvent.click(screen.getByText('Data Sources Status'));
    expect(screen.getAllByText(/Last fetched: 2026-08-01/).length).toBe(2);
    expect(screen.getByText(/Public data gap/)).toBeDefined();
  });

  it('renders an empty source list without throwing', () => {
    render(<DataStatusPanel sources={[]} />);
    expect(screen.getByText('Data Sources Status')).toBeDefined();
  });
});
