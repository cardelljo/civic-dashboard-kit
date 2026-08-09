'use client';

import { useState } from 'react';
import {
  CheckCircle2, AlertCircle, Clock, ChevronDown, ChevronUp,
  ExternalLink, FileText, FlaskConical, RefreshCw,
} from 'lucide-react';

import { resolveStatus, type DataStatus } from './types';

export interface DataSource {
  id: string;
  label: string;
  section: string;
  isSample: boolean;
  status?: DataStatus;
  lastFetched: string | null;
  fetchedBy: string | null;
  howToUpdate?: string;
  apiUrl?: string;
  pdfIndexUrl?: string;
  notes: string;
}

interface Props {
  sources: DataSource[];
}

function StatusIcon({ status, lastFetched }: { status: DataStatus; lastFetched: string | null }) {
  if (status === 'live' && lastFetched) {
    return <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />;
  }
  if (status === 'live' && !lastFetched) {
    return <Clock className="w-4 h-4 text-amber-400 shrink-0" />;
  }
  if (status === 'mixed') {
    return <AlertCircle className="w-4 h-4 text-blue-500 shrink-0" />;
  }
  if (status === 'gap') {
    return <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />;
  }
  if (status === 'manual' || status === 'report-backed') {
    return <FileText className="w-4 h-4 text-indigo-500 shrink-0" />;
  }
  return <FlaskConical className="w-4 h-4 text-amber-500 shrink-0" />;
}

function StatusBadge({ status }: { status: DataStatus }) {
  if (status === 'live') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-700">
        <CheckCircle2 className="w-3 h-3" /> Live
      </span>
    );
  }
  if (status === 'mixed') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
        <AlertCircle className="w-3 h-3" /> Mixed
      </span>
    );
  }
  if (status === 'gap') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
        <AlertCircle className="w-3 h-3" /> Data Gap
      </span>
    );
  }
  if (status === 'manual' || status === 'report-backed') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800">
        <FileText className="w-3 h-3" /> Report
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
      <FlaskConical className="w-3 h-3" /> Sample
    </span>
  );
}

export default function DataStatusPanel({ sources }: Props) {
  const [open, setOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const counts = sources.reduce(
    (acc, src) => {
      acc[resolveStatus(src)] += 1;
      return acc;
    },
    { live: 0, mixed: 0, sample: 0, gap: 0, manual: 0, 'report-backed': 0 } as Record<DataStatus, number>,
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-2">
      <div className="border border-amber-200 rounded-2xl overflow-hidden bg-white shadow-sm">
        {/* Collapsed header — always visible */}
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-amber-50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <RefreshCw className="w-4 h-4 text-amber-500" />
            <span className="text-sm font-semibold text-slate-700">
              Data Sources Status
            </span>
            <span className="flex gap-2">
              {counts.live > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
                  {counts.live} live
                </span>
              )}
              {counts.mixed > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                  {counts.mixed} mixed
                </span>
              )}
              {counts.gap > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium">
                  {counts.gap} gaps
                </span>
              )}
              {counts.sample > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                  {counts.sample} sample
                </span>
              )}
              {counts.manual + counts['report-backed'] > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">
                  {counts.manual + counts['report-backed']} report
                </span>
              )}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>{open ? 'Hide details' : 'Show details'}</span>
            {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {/* Expanded panel */}
        {open && (
          <div className="border-t border-amber-100 divide-y divide-slate-100">
            {sources.map((src) => {
              const status = resolveStatus(src);
              return (
              <div key={src.id} className="px-5 py-3">
                <button
                  className="w-full flex items-start justify-between gap-4 text-left"
                  onClick={() => setExpandedId(expandedId === src.id ? null : src.id)}
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <StatusIcon status={status} lastFetched={src.lastFetched} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-slate-800">{src.label}</span>
                        <StatusBadge status={status} />
                        <span className="text-xs text-slate-400">→ {src.section}</span>
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {status === 'gap'
                          ? 'Public data gap — verified dataset not yet available'
                          : status === 'manual' || status === 'report-backed'
                          ? 'Report-backed source — manually reviewed, not a live feed'
                          : status === 'mixed'
                          ? 'Verified source data plus fields needing confirmation'
                          : status === 'sample'
                          ? 'Using estimated sample values'
                          : src.lastFetched
                          ? `Last fetched: ${src.lastFetched}`
                          : 'Live — not yet fetched'}
                      </div>
                    </div>
                  </div>
                  <ChevronDown
                    className={`w-4 h-4 text-slate-400 shrink-0 mt-0.5 transition-transform ${
                      expandedId === src.id ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {/* Expanded detail */}
                {expandedId === src.id && (
                  <div className="mt-3 ml-7 space-y-2 text-xs text-slate-600 bg-slate-50 rounded-xl p-3">
                    <div>
                      <span className="font-semibold text-slate-700">Script: </span>
                      <code className="bg-slate-200 px-1 py-0.5 rounded text-slate-800">{src.fetchedBy ?? 'not automated yet'}</code>
                    </div>

                    {src.notes && (
                      <div>
                        <span className="font-semibold text-slate-700">Current status: </span>
                        {src.notes}
                      </div>
                    )}

                    {src.howToUpdate && (
                      <div>
                        <span className="font-semibold text-slate-700">How to update: </span>
                        <span className="text-teal-700">{src.howToUpdate}</span>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2 pt-1">
                      {src.apiUrl && (
                        <a
                          href={src.apiUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-brand-blue hover:underline"
                        >
                          Verify API endpoint <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                      {src.pdfIndexUrl && (
                        <a
                          href={src.pdfIndexUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-brand-blue hover:underline"
                        >
                          PDF report index <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
