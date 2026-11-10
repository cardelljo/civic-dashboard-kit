import { describe, expect, it } from 'vitest';

import { decimalYear, termMarkers, type OfficeholderSeries } from '../../ui';

// Invented jurisdiction: the kit carries no real place's officeholders.
const series: OfficeholderSeries = {
  office: 'Mayor',
  terms: [
    { name: 'Avery', start: '1992-01-01', end: '2009-07-30' },
    { name: 'Interim', start: '2009-07-31', end: '2009-10-29', acting: true },
    { name: 'Blake', start: '2009-10-30', end: '2015-12-31' },
    { name: 'Casey', start: '2016-01-01', end: '2023-12-31' },
    { name: 'Drew', start: '2024-01-01' },
  ],
};

describe('decimalYear', () => {
  it('converts calendar dates and rejects bad ones', () => {
    expect(decimalYear('2016-01-01')).toBe(2016);
    expect(decimalYear('2009-10-30')).toBeCloseTo(2009 + 302 / 365, 6);
    expect(() => decimalYear('2016-1-1')).toThrow();
    expect(() => decimalYear('2023-02-30')).toThrow();
  });
});

describe('termMarkers', () => {
  it('clips to the range, flags a term that began earlier, and drops acting terms', () => {
    const got = termMarkers(series, { from: 2000.5, to: 2025.5 });
    expect(got.map(m => m.name)).toEqual(['Avery', 'Blake', 'Casey', 'Drew']);
    expect(got[0]).toMatchObject({ start: 2000.5, startsBeforeRange: true });
    expect(got[1].startsBeforeRange).toBe(false);
    expect(got[3].end).toBe(2025.5); // open term runs to the range end
    expect(got[2].labelAt).toBeCloseTo((2016 + decimalYear('2023-12-31')) / 2, 6);
  });

  it('can include acting terms, but still hides ones shorter than minDays', () => {
    expect(termMarkers(series, { from: 2000, to: 2026, includeActing: true }).map(m => m.name))
      .not.toContain('Interim');
    expect(termMarkers(series, { from: 2000, to: 2026, includeActing: true, minDays: 30 }).map(m => m.name))
      .toContain('Interim');
  });

  it('drops terms outside the range and a sliver clipped below minDays', () => {
    expect(termMarkers(series, { from: 2024.1, to: 2026 }).map(m => m.name)).toEqual(['Drew']);
    expect(termMarkers(series, { from: 2023.9, to: 2026 }).map(m => m.name)).toEqual(['Drew']);
  });

  it('returns nothing for a geography without officeholders or an empty range', () => {
    expect(termMarkers(undefined, { from: 2000, to: 2025 })).toEqual([]);
    expect(termMarkers(series, { from: 2025, to: 2025 })).toEqual([]);
  });
});
