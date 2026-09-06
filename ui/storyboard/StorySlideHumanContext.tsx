import React from 'react';
import type { StoryboardSlideHumanContext } from './types';

export interface StorySlideHumanContextProps {
  slide: StoryboardSlideHumanContext;
}

export default function StorySlideHumanContext({ slide }: StorySlideHumanContextProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <span className="inline-block px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 dark:bg-emerald-400/20 dark:text-emerald-300">
          Slide 1 of 4 • Human Context & Lived Reality
        </span>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white leading-snug">
          {slide.headline}
        </h2>
      </div>

      <p className="text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
        {slide.narrative}
      </p>

      {/* Primary KPI Hero Card */}
      <div className="p-6 rounded-2xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {slide.primaryStat.label}
          </div>
          <div className="text-4xl sm:text-5xl font-black text-emerald-600 dark:text-emerald-400 mt-1">
            {slide.primaryStat.value}
          </div>
          {slide.primaryStat.changeLabel && (
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-medium">
              {slide.primaryStat.changeLabel}
            </div>
          )}
        </div>

        {slide.primaryStat.benchmarkLabel && (
          <div className="sm:text-right border-t sm:border-t-0 sm:border-l border-slate-200 dark:border-slate-700 pt-3 sm:pt-0 sm:pl-6">
            <div className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              {slide.primaryStat.benchmarkLabel}
            </div>
            <div className="text-2xl font-bold text-slate-800 dark:text-slate-200 mt-0.5">
              {slide.primaryStat.benchmarkValue}
            </div>
          </div>
        )}
      </div>

      {/* Anchor Quote */}
      {slide.humanAnchorQuote && (
        <blockquote className="p-4 rounded-xl bg-emerald-50/80 dark:bg-emerald-950/40 border-l-4 border-emerald-500 dark:border-emerald-400 text-sm text-slate-800 dark:text-emerald-200 italic leading-relaxed">
          "{slide.humanAnchorQuote}"
          {slide.humanAnchorAttribution && (
            <footer className="mt-1 text-xs not-italic font-semibold text-slate-600 dark:text-emerald-300">
              — {slide.humanAnchorAttribution}
            </footer>
          )}
        </blockquote>
      )}
    </div>
  );
}
