'use client';

import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import type { StoryboardStory, AudiencePersona } from './types';
import StoryboardPresenter from './StoryboardPresenter';

export interface StoryboardModalProps {
  isOpen: boolean;
  onClose: () => void;
  story: StoryboardStory | null;
  initialPersona?: AudiencePersona;
  initialSlideIndex?: number;
}

export default function StoryboardModal({
  isOpen,
  onClose,
  story,
  initialPersona = 'resident',
  initialSlideIndex = 0,
}: StoryboardModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !story) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8 bg-slate-950/80 backdrop-blur-sm transition-opacity"
      role="dialog"
      aria-modal="true"
      aria-labelledby="storyboard-modal-title"
    >
      <div className="relative w-full max-w-4xl max-h-[92vh] flex flex-col">
        {/* Floating Close Button */}
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 z-10 p-2 rounded-full bg-slate-800 text-slate-200 hover:text-white hover:bg-slate-700 shadow-lg border border-slate-700 transition-colors"
          aria-label="Close storyboard"
        >
          <X className="w-4 h-4" />
        </button>

        <StoryboardPresenter
          story={story}
          initialPersona={initialPersona}
          initialSlideIndex={initialSlideIndex}
          className="h-full"
        />
      </div>
    </div>
  );
}
