'use client';

import { useId, useState } from 'react';

/** Area kinds are shared; jurisdiction names belong to the consuming dashboard. */
export type GeographyLevel =
  | 'city'
  | 'county'
  | 'school-district'
  | 'metro'
  | 'state'
  | 'nation'
  | 'peer-ring';

export type JurisdictionConfig = Partial<Record<GeographyLevel, {
  name: string;
  note?: string;
}>>;

export type GeographyTagProps = {
  level: GeographyLevel;
  jurisdiction: JurisdictionConfig;
};

const LEVEL_NAMES: Record<GeographyLevel, string> = {
  city: 'City',
  county: 'County',
  'school-district': 'School district',
  metro: 'Metro',
  state: 'State',
  nation: 'Nation',
  'peer-ring': 'Peer ring',
};

/** Inline geography chip; a note opens on focus or tap and closes on blur/Escape. */
export default function GeographyTag({ level, jurisdiction }: GeographyTagProps) {
  const [open, setOpen] = useState(false);
  const noteId = useId();
  const known = Object.prototype.hasOwnProperty.call(LEVEL_NAMES, level);
  const entry = known && Object.prototype.hasOwnProperty.call(jurisdiction, level)
    ? jurisdiction[level]
    : undefined;
  const name = entry?.name?.trim() || (known ? LEVEL_NAMES[level] : 'Unknown geography');
  const note = entry?.note?.trim();
  const chipClass = 'inline-flex rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-xs leading-normal text-slate-700';

  if (!note) return <span className={chipClass}>{name}</span>;

  return (
    <span className="relative inline-block">
      <button
        type="button"
        className={`${chipClass} cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2`}
        aria-expanded={open}
        aria-controls={noteId}
        aria-describedby={open ? noteId : undefined}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
        }}
      >
        {name}
      </button>
      <span
        id={noteId}
        role="note"
        hidden={!open}
        className="absolute left-0 top-full z-10 mt-1 w-56 max-w-[80vw] rounded border border-slate-300 bg-white p-2 text-xs leading-normal text-slate-700 shadow-md"
      >
        {note}
      </span>
    </span>
  );
}
