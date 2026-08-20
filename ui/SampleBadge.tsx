import { AlertCircle, FileText, FlaskConical } from 'lucide-react';

import { resolveStatus, type DataStatus } from './types';

/**
 * Small badge shown in section headers when the section is not fully live.
 */
export default function SampleBadge({ isSample, status }: { isSample: boolean; status?: DataStatus }) {
  const resolvedStatus = resolveStatus({ isSample, status });

  if (resolvedStatus === 'live') return null;

  if (resolvedStatus === 'mixed') {
    return (
      <span
        title="This section combines verified source data with fields that still need direct partner confirmation."
        className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200 cursor-help"
      >
        <AlertCircle className="w-3 h-3" />
        Mixed Sources
      </span>
    );
  }

  if (resolvedStatus === 'gap') {
    return (
      <span
        title="This section primarily documents a public data gap rather than showing a verified live dataset."
        className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200 cursor-help"
      >
        <AlertCircle className="w-3 h-3" />
        Data Gap
      </span>
    );
  }

  if (resolvedStatus === 'manual' || resolvedStatus === 'report-backed') {
    return (
      <span
        title="This section is backed by a published report or manually reviewed source, not a live data feed."
        className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200 cursor-help"
      >
        <FileText className="w-3 h-3" />
        Report-Backed
      </span>
    );
  }

  return (
    <span
      title="This section is using estimated sample data. See the Data Sources Status panel above for details."
      className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 cursor-help"
    >
      <FlaskConical className="w-3 h-3" />
      Sample Data
    </span>
  );
}
