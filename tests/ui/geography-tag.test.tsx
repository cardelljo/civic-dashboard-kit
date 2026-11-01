import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GeographyTag, SourceLine, type GeographyLevel, type JurisdictionConfig } from '../../ui';

const jurisdiction: JurisdictionConfig = {
  metro: { name: 'River metro', note: 'Nine surrounding counties.' },
  city: { name: 'River city' },
};

describe('GeographyTag', () => {
  it('renders an explicit fallback for an unknown runtime level', () => {
    render(<GeographyTag level={'planet' as GeographyLevel} jurisdiction={jurisdiction} />);
    expect(screen.getByText('Unknown geography')).toBeDefined();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('renders the generic level when the jurisdiction has no entry', () => {
    render(<GeographyTag level="county" jurisdiction={jurisdiction} />);
    expect(screen.getByText('County')).toBeDefined();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('lets two jurisdictions name the same level differently', () => {
    render(<>
      <GeographyTag level="city" jurisdiction={jurisdiction} />
      <GeographyTag level="city" jurisdiction={{ city: { name: 'Lake city' } }} />
    </>);
    expect(screen.getByText('River city')).toBeDefined();
    expect(screen.getByText('Lake city')).toBeDefined();
  });

  it('opens the note on keyboard focus, dismisses with Escape, and closes on blur', () => {
    render(<GeographyTag level="metro" jurisdiction={jurisdiction} />);
    const chip = screen.getByRole('button', { name: 'River metro' });
    expect(chip.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByRole('note')).toBeNull();
    fireEvent.focus(chip);
    expect(chip.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('note').textContent).toBe('Nine surrounding counties.');
    expect(chip.getAttribute('aria-describedby')).toBe(screen.getByRole('note').id);
    fireEvent.keyDown(chip, { key: 'Escape' });
    expect(screen.queryByRole('note')).toBeNull();
    fireEvent.blur(chip);
    fireEvent.focus(chip);
    fireEvent.blur(chip);
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('opens the note on tap/click without requiring hover', () => {
    render(<GeographyTag level="metro" jurisdiction={jurisdiction} />);
    fireEvent.click(screen.getByRole('button', { name: 'River metro' }));
    expect(screen.getByRole('note').textContent).toBe('Nine surrounding counties.');
  });

  it('renders a noninteractive chip when no note is supplied', () => {
    render(<GeographyTag level="city" jurisdiction={jurisdiction} />);
    expect(screen.getByText('River city')).toBeDefined();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('does not treat inherited object properties as known levels', () => {
    render(<GeographyTag level={'toString' as GeographyLevel} jurisdiction={jurisdiction} />);
    expect(screen.getByText('Unknown geography')).toBeDefined();
  });
});

describe('SourceLine geography chips', () => {
  it('renders a configured chip with source and vintage without changing punctuation', () => {
    const { container } = render(<SourceLine source="Census" vintage="2023"
      geography={{ level: 'city', jurisdiction }} />);
    expect(container.textContent).toBe('Source: Census · 2023 · River city');
  });

  it('supports a note inside the geography slot and vintage-only attribution', () => {
    const { container } = render(<SourceLine vintage="2023"
      geography={{ level: 'metro', jurisdiction }} />);
    const chip = screen.getByRole('button', { name: 'River metro' });
    expect(chip.parentElement?.parentElement?.tagName).toBe('P');
    expect(container.querySelector('p')?.textContent?.startsWith('Source: 2023 · River metro')).toBe(true);
    fireEvent.click(chip);
    expect(screen.getByRole('note').textContent).toBe('Nine surrounding counties.');
    expect(container.textContent?.match(/2023/g)).toHaveLength(1);
  });
});
