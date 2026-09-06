'use client';

import React, { useState } from 'react';
import { Copy, Check, ExternalLink, Landmark, Calendar, MapPin } from 'lucide-react';
import type { StoryboardSlideCivicAction } from './types';

export interface StorySlideCivicActionProps {
  slide: StoryboardSlideCivicAction;
}

export default function StorySlideCivicAction({ slide }: StorySlideCivicActionProps) {
  const [copied, setCopied] = useState(false);

  const fullTestimonyText = `
Public Testimony Script: ${slide.headline}
Target Body: ${slide.responsibleBody.name}

Talking Points:
${slide.talkingPoints.map((pt, i) => `${i + 1}. ${pt}`).join('\n')}

Policy Asks:
${slide.policyAsks.map((ask) => `- ${ask.tier ? `[${ask.tier}] ` : ''}${ask.ask}`).join('\n')}
  `.trim();

  const handleCopy = () => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(fullTestimonyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <span className="inline-block px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-rose-500/10 text-rose-600 dark:bg-rose-400/20 dark:text-rose-300">
          Slide 4 of 4 • Direct Civic Action & Advocacy
        </span>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white leading-snug">
          {slide.headline}
        </h2>
      </div>

      <p className="text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
        {slide.narrative}
      </p>

      {/* Target Body & Schedule Info Card */}
      <div className="p-4 sm:p-5 rounded-2xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Landmark className="w-5 h-5 text-slate-700 dark:text-slate-300" />
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              {slide.responsibleBody.name}
            </h3>
          </div>
          {slide.responsibleBody.publicCommentSignupUrl && (
            <a
              href={slide.responsibleBody.publicCommentSignupUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline"
            >
              Sign Up to Speak <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-600 dark:text-slate-300 pt-2 border-t border-slate-200 dark:border-slate-700">
          {slide.responsibleBody.meetingSchedule && (
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-400 shrink-0" />
              <span>{slide.responsibleBody.meetingSchedule}</span>
            </div>
          )}
          {slide.responsibleBody.location && (
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-slate-400 shrink-0" />
              <span>{slide.responsibleBody.location}</span>
            </div>
          )}
        </div>
      </div>

      {/* Policy Asks & Demands */}
      <div className="space-y-2.5">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Concrete Policy Demands
        </div>
        <div className="space-y-2">
          {slide.policyAsks.map((item, idx) => (
            <div
              key={idx}
              className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 flex items-start gap-3"
            >
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5">
                {idx + 1}
              </span>
              <div>
                {item.tier && (
                  <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-0.5">
                    {item.tier}
                  </span>
                )}
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {item.ask}
                </div>
                {item.targetOfficial && (
                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Target: {item.targetOfficial}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Public Testimony Script Box */}
      <div className="p-4 rounded-xl bg-slate-900 text-white space-y-3 shadow-md">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold uppercase tracking-wider text-emerald-400">
            3-Minute Public Comment Script
          </div>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition-colors"
            aria-label="Copy testimony script"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied!' : 'Copy Script'}
          </button>
        </div>

        <ol className="list-decimal list-inside space-y-1.5 text-xs sm:text-sm text-slate-300 leading-relaxed">
          {slide.talkingPoints.map((point, index) => (
            <li key={index} className="pl-1">
              <span className="text-slate-100">{point}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
