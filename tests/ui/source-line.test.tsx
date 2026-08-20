import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SourceLine } from '../../ui';

/**
 * These assert the rendered *text* of the standard line, separator placement
 * included, because that is what the standard actually fixes. A change to the
 * form should have to change a test.
 */

function lineText(ui: React.ReactElement): string {
  const { container } = render(ui);
  // Collapse whitespace so JSX line breaks don't affect the comparison.
  return (container.textContent ?? '').replace(/\s+/g, ' ').trim();
}

describe('SourceLine', () => {
  it('renders source, vintage, and geography separated by middots', () => {
    expect(
      lineText(
        <SourceLine
          source="BEA Regional GDP"
          vintage="2023"
          geography="Memphis MSA"
        />,
      ),
    ).toBe('Source: BEA Regional GDP · 2023 · Memphis MSA');
  });

  it('drops an absent vintage without leaving a stray separator', () => {
    expect(
      lineText(<SourceLine source="TDOE TCAP Assessment Files" geography="MSCS" />),
    ).toBe('Source: TDOE TCAP Assessment Files · MSCS');
  });

  it('drops an absent geography', () => {
    expect(lineText(<SourceLine source="Shelby County Jail Report" vintage="March 2026" />))
      .toBe('Source: Shelby County Jail Report · March 2026');
  });

  it('promotes vintage to the primary slot when there is no source name', () => {
    // 901economy's shape today: no per-row publisher name available.
    expect(lineText(<SourceLine vintage="2023 ACS 5-year" />)).toBe(
      'Source: 2023 ACS 5-year',
    );
  });

  it('does not repeat the vintage when it is standing in as the primary', () => {
    const text = lineText(<SourceLine vintage="2023 ACS 5-year" geography="Shelby County" />);
    expect(text).toBe('Source: 2023 ACS 5-year · Shelby County');
    expect(text.match(/2023 ACS 5-year/g)).toHaveLength(1);
  });

  it('links the source name, opening in a new tab safely', () => {
    render(
      <SourceLine
        source="Shelby County Jail Report"
        vintage="March 2026"
        sourceUrl="https://example.gov/jail-report.pdf"
      />,
    );
    const link = screen.getByRole('link', { name: /Shelby County Jail Report/ });
    expect(link.getAttribute('href')).toBe('https://example.gov/jail-report.pdf');
    expect(link.getAttribute('target')).toBe('_blank');
    // Without noopener the opened page gets a handle on window.opener.
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('links the vintage when the vintage is the primary', () => {
    render(<SourceLine vintage="2023 ACS 5-year" sourceUrl="https://example.gov/acs" />);
    expect(screen.getByRole('link', { name: /2023 ACS 5-year/ })).toBeDefined();
  });

  it('renders no link when sourceUrl is absent or null', () => {
    const { container: withoutUrl } = render(<SourceLine source="MPD Open Data Hub" />);
    expect(withoutUrl.querySelector('a')).toBeNull();

    const { container: withNull } = render(
      <SourceLine source="MPD Open Data Hub" sourceUrl={null} />,
    );
    expect(withNull.querySelector('a')).toBeNull();
  });

  it('renders a caveat after the attribution, not inside it', () => {
    expect(
      lineText(
        <SourceLine
          source="TDOE TCAP Assessment Files"
          vintage="2023-24"
          caveat="2019-20 canceled and 2020-21 disrupted by COVID; treat those years with caution."
        />,
      ),
    ).toBe(
      'Source: TDOE TCAP Assessment Files · 2023-24 2019-20 canceled and ' +
        '2020-21 disrupted by COVID; treat those years with caution.',
    );
  });

  it('accepts a caveat containing markup, which justice needs for links', () => {
    render(
      <SourceLine
        source="TBI School Crime Report"
        caveat={<>Only the Clearances table is machine-extracted. <a href="https://example.gov/r">Read the full report</a></>}
      />,
    );
    expect(screen.getByRole('link', { name: 'Read the full report' })).toBeDefined();
  });

  it('defaults to the data-note class every dashboard defines, and honors an override', () => {
    const { container: byDefault } = render(<SourceLine source="X" />);
    expect(byDefault.querySelector('p')?.className).toBe('data-note');

    const { container: overridden } = render(
      <SourceLine source="X" className="section-subheader" />,
    );
    expect(overridden.querySelector('p')?.className).toBe('section-subheader');
  });

  it('shows a visible marker rather than vanishing when provenance is missing', () => {
    // Unreachable through the prop types; reachable in 901justice, which builds
    // with ignoreBuildErrors. A silently empty line is the failure mode this
    // contract exists to prevent, so it must render something.
    const noProvenance = {} as React.ComponentProps<typeof SourceLine>;
    expect(lineText(<SourceLine {...noProvenance} />)).toBe('Source: not recorded');
  });
});
