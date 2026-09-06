import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import type { StoryboardStory, AudiencePersona, StoryboardSlide } from './types';
import { DEFAULT_PERSONAS } from './types';
import StorySlideHumanContext from './StorySlideHumanContext';
import StorySlideIntersections from './StorySlideIntersections';
import StorySlideRootCauses from './StorySlideRootCauses';
import StorySlideCivicAction from './StorySlideCivicAction';

export interface StoryboardPresenterProps {
  story: StoryboardStory;
  initialPersona?: AudiencePersona;
  initialSlideIndex?: number;
  onPersonaChange?: (persona: AudiencePersona) => void;
  onSlideChange?: (slideIndex: number) => void;
  className?: string;
  showHeader?: boolean;
}

export default function StoryboardPresenter({
  story,
  initialPersona = 'resident',
  initialSlideIndex = 0,
  onPersonaChange,
  onSlideChange,
  className = '',
  showHeader = true,
}: StoryboardPresenterProps) {
  const [activePersona, setActivePersona] = useState<AudiencePersona>(initialPersona);
  const [slideIndex, setSlideIndex] = useState<number>(initialSlideIndex);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);

  const activeSlides: StoryboardSlide[] = useMemo(() => {
    if (story.personaVariations && story.personaVariations[activePersona]) {
      return story.personaVariations[activePersona]!;
    }
    return story.slides;
  }, [story, activePersona]);

  const currentSlide = activeSlides[slideIndex] || activeSlides[0];

  const handlePersonaSelect = useCallback(
    (persona: AudiencePersona) => {
      setActivePersona(persona);
      onPersonaChange?.(persona);
    },
    [onPersonaChange]
  );

  const goToSlide = useCallback(
    (index: number) => {
      const clamped = Math.max(0, Math.min(3, index));
      setSlideIndex(clamped);
      onSlideChange?.(clamped);
    },
    [onSlideChange]
  );

  const nextSlide = useCallback(() => goToSlide(slideIndex + 1), [goToSlide, slideIndex]);
  const prevSlide = useCallback(() => goToSlide(slideIndex - 1), [goToSlide, slideIndex]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') {
        nextSlide();
      } else if (e.key === 'ArrowLeft') {
        prevSlide();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nextSlide, prevSlide]);

  // Mobile touch swipe handling
  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStartX(e.touches[0].clientX);
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX === null) return;
    const touchEndX = e.changedTouches[0].clientX;
    const diff = touchStartX - touchEndX;
    if (diff > 50) {
      nextSlide();
    } else if (diff < -50) {
      prevSlide();
    }
    setTouchStartX(null);
  };

  return (
    <div
      className={`flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl overflow-hidden ${className}`}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Top Header & Persona Switcher */}
      {showHeader && (
        <div className="p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              <Sparkles className="w-3.5 h-3.5" /> Civic Data Storyboard
              {story.geography && (
                <span className="text-slate-400 dark:text-slate-500 font-normal">
                  • {story.geography}
                </span>
              )}
            </div>
            <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white mt-0.5">
              {story.title}
            </h1>
            {story.subtitle && (
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {story.subtitle}
              </p>
            )}
          </div>

          {/* Persona selector tabs */}
          <div className="flex items-center gap-1 bg-slate-200/80 dark:bg-slate-800 p-1 rounded-xl self-start sm:self-auto overflow-x-auto max-w-full">
            {DEFAULT_PERSONAS.map((p) => (
              <button
                key={p.id}
                onClick={() => handlePersonaSelect(p.id)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all whitespace-nowrap ${
                  activePersona === p.id
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
                title={p.description}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Slide Body Stage */}
      <div className="flex-1 p-6 sm:p-8 lg:p-10 overflow-y-auto">
        {currentSlide.type === 'human_context' && (
          <StorySlideHumanContext slide={currentSlide} />
        )}
        {currentSlide.type === 'intersections' && (
          <StorySlideIntersections slide={currentSlide} />
        )}
        {currentSlide.type === 'root_causes' && (
          <StorySlideRootCauses slide={currentSlide} />
        )}
        {currentSlide.type === 'civic_action' && (
          <StorySlideCivicAction slide={currentSlide} />
        )}
      </div>

      {/* Bottom Navigation Control Bar */}
      <div className="p-4 sm:p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 flex items-center justify-between gap-4">
        <button
          onClick={prevSlide}
          disabled={slideIndex === 0}
          className="inline-flex items-center gap-1 px-4 py-2 text-xs sm:text-sm font-semibold rounded-xl text-slate-700 dark:text-slate-300 hover:bg-slate-200/60 dark:hover:bg-slate-800 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          aria-label="Previous slide"
        >
          <ChevronLeft className="w-4 h-4" /> Previous
        </button>

        {/* Step Indicator Dots */}
        <div className="flex items-center gap-2">
          {[0, 1, 2, 3].map((idx) => (
            <button
              key={idx}
              onClick={() => goToSlide(idx)}
              className={`h-2.5 rounded-full transition-all ${
                slideIndex === idx
                  ? 'w-8 bg-emerald-600 dark:bg-emerald-400'
                  : 'w-2.5 bg-slate-300 dark:bg-slate-700 hover:bg-slate-400 dark:hover:bg-slate-600'
              }`}
              aria-label={`Jump to slide ${idx + 1}`}
            />
          ))}
        </div>

        <button
          onClick={nextSlide}
          disabled={slideIndex === 3}
          className="inline-flex items-center gap-1 px-4 py-2 text-xs sm:text-sm font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white dark:bg-emerald-500 dark:hover:bg-emerald-600 disabled:opacity-30 disabled:pointer-events-none transition-colors shadow-sm"
          aria-label="Next slide"
        >
          Next <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Citations footer */}
      {story.citations && story.citations.length > 0 && (
        <div className="px-6 py-2.5 bg-slate-100/70 dark:bg-slate-950 border-t border-slate-200/60 dark:border-slate-800/60 text-[11px] text-slate-500 dark:text-slate-400 flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="font-semibold text-slate-700 dark:text-slate-300">Sources:</span>
          {story.citations.map((c, i) => (
            <span key={i}>
              {c.metricName}: {c.source} ({c.vintage})
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
