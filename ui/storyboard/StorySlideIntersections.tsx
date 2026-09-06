import React from 'react';
import type { StoryboardSlideIntersections } from './types';

export interface StorySlideIntersectionsProps {
  slide: StoryboardSlideIntersections;
}

const DOMAIN_BADGES: Record<string, { bg: string; text: string; label: string }> = {
  education: { bg: 'bg-emerald-500/10 dark:bg-emerald-400/20', text: 'text-emerald-700 dark:text-emerald-300', label: 'Education' },
  justice: { bg: 'bg-amber-500/10 dark:bg-amber-400/20', text: 'text-amber-700 dark:text-amber-300', label: 'Youth & Justice' },
  economy: { bg: 'bg-blue-500/10 dark:bg-blue-400/20', text: 'text-blue-700 dark:text-blue-300', label: 'Economy & Wages' },
  housing: { bg: 'bg-purple-500/10 dark:bg-purple-400/20', text: 'text-purple-700 dark:text-purple-300', label: 'Housing & Eviction' },
  health: { bg: 'bg-rose-500/10 dark:bg-rose-400/20', text: 'text-rose-700 dark:text-rose-300', label: 'Community Health' },
};

export default function StorySlideIntersections({ slide }: StorySlideIntersectionsProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <span className="inline-block px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-blue-500/10 text-blue-600 dark:bg-blue-400/20 dark:text-blue-300">
          Slide 2 of 4 • Cross-Domain Intersections
        </span>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white leading-snug">
          {slide.headline}
        </h2>
      </div>

      <p className="text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
        {slide.narrative}
      </p>

      {/* Grid of correlated metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {slide.crossDomainMetrics.map((item, idx) => {
          const badge = DOMAIN_BADGES[item.domain] || {
            bg: 'bg-slate-100 dark:bg-slate-800',
            text: 'text-slate-700 dark:text-slate-300',
            label: item.domain,
          };
          return (
            <div
              key={idx}
              className="p-5 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 flex flex-col justify-between"
            >
              <div>
                <span
                  className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wide mb-2 ${badge.bg} ${badge.text}`}
                >
                  {badge.label}
                </span>
                <div className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white mt-1">
                  {item.value}
                </div>
                <div className="text-xs sm:text-sm font-medium text-slate-600 dark:text-slate-300 mt-1">
                  {item.label}
                </div>
              </div>
              {item.contextNote && (
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-3 pt-2 border-t border-slate-200/80 dark:border-slate-700/80">
                  {item.contextNote}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {slide.intersectionTakeaway && (
        <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs sm:text-sm text-slate-700 dark:text-slate-300">
          <strong className="text-slate-900 dark:text-white">Compounded Impact:</strong> {slide.intersectionTakeaway}
        </div>
      )}
    </div>
  );
}
