import React from 'react';
import type { StoryboardSlideRootCauses } from './types';

export interface StorySlideRootCausesProps {
  slide: StoryboardSlideRootCauses;
}

export default function StorySlideRootCauses({ slide }: StorySlideRootCausesProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <span className="inline-block px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500/10 text-amber-600 dark:bg-amber-400/20 dark:text-amber-300">
          Slide 3 of 4 • Root Causes & Structural Drivers
        </span>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white leading-snug">
          {slide.headline}
        </h2>
      </div>

      <p className="text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
        {slide.narrative}
      </p>

      {/* Structural Drivers List */}
      <div className="space-y-3">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Key Systemic & Policy Drivers
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {slide.structuralDrivers.map((driver, idx) => (
            <div
              key={idx}
              className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 flex flex-col justify-between"
            >
              <div>
                {driver.tag && (
                  <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 mb-1.5">
                    {driver.tag}
                  </span>
                )}
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  {driver.title}
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-normal">
                  {driver.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {slide.fundingContext && (
        <div className="p-4 rounded-xl bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-xs sm:text-sm text-amber-900 dark:text-amber-200 leading-relaxed">
          <strong className="text-amber-950 dark:text-amber-100">Funding & Budget Reality:</strong> {slide.fundingContext}
        </div>
      )}
    </div>
  );
}
