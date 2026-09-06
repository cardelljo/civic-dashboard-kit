/**
 * Types and schemas for the Civic Storyboard & Scrollytelling Engine.
 *
 * Designed to power interactive 4-slide data narratives across
 * 901education, 901justice, 901economy, and future civic dashboards.
 *
 * Arc structure inspired by decriminalizepoverty.org/present1/:
 *  1. Human Context (Lived reality, human scaling)
 *  2. Cross-Domain Intersections (Compounded data indicators)
 *  3. Root Causes (Funding mechanisms, structural drivers)
 *  4. Civic Action (Responsible entities, policy demands, testimony script)
 */

export type AudiencePersona = 'resident' | 'organizer' | 'journalist' | 'policymaker';

export interface PersonaConfig {
  id: AudiencePersona;
  label: string;
  description: string;
}

export const DEFAULT_PERSONAS: PersonaConfig[] = [
  {
    id: 'resident',
    label: 'Resident / Parent',
    description: 'Human-scaled context, everyday language, and direct family/community impact.',
  },
  {
    id: 'organizer',
    label: 'Organizer',
    description: 'Racial disparities, community mobilization points, and meeting testimony scripts.',
  },
  {
    id: 'journalist',
    label: 'Journalist',
    description: 'Fact-checked provenance, multi-year comparisons, and statutory citations.',
  },
  {
    id: 'policymaker',
    label: 'Policymaker',
    description: 'Statutory levers, budget impact, agency jurisdictions, and policy recommendations.',
  },
];

export interface StoryboardSlideHumanContext {
  slideNumber: 1;
  type: 'human_context';
  headline: string;
  narrative: string;
  primaryStat: {
    label: string;
    value: string | number;
    benchmarkLabel?: string;
    benchmarkValue?: string | number;
    changeLabel?: string;
  };
  humanAnchorQuote?: string;
  humanAnchorAttribution?: string;
}

export interface StoryboardSlideIntersections {
  slideNumber: 2;
  type: 'intersections';
  headline: string;
  narrative: string;
  crossDomainMetrics: Array<{
    domain: 'education' | 'justice' | 'economy' | 'health' | 'housing';
    label: string;
    value: string | number;
    contextNote?: string;
  }>;
  intersectionTakeaway?: string;
}

export interface StoryboardSlideRootCauses {
  slideNumber: 3;
  type: 'root_causes';
  headline: string;
  narrative: string;
  structuralDrivers: Array<{
    title: string;
    description: string;
    tag?: string;
  }>;
  fundingContext?: string;
}

export interface PolicyAskItem {
  tier?: 'Immediate Budget Ask' | 'Structural Policy Reform' | 'Transparency Mandate' | string;
  ask: string;
  targetOfficial?: string;
}

export interface ResponsibleBodyInfo {
  name: string;
  jurisdiction?: string;
  meetingSchedule?: string;
  location?: string;
  publicCommentSignupUrl?: string;
  contactEmail?: string;
  phone?: string;
}

export interface StoryboardSlideCivicAction {
  slideNumber: 4;
  type: 'civic_action';
  headline: string;
  narrative: string;
  policyAsks: PolicyAskItem[];
  responsibleBody: ResponsibleBodyInfo;
  talkingPoints: string[];
}

export type StoryboardSlide =
  | StoryboardSlideHumanContext
  | StoryboardSlideIntersections
  | StoryboardSlideRootCauses
  | StoryboardSlideCivicAction;

export interface StoryboardStory {
  id: string;
  topic: string;
  title: string;
  subtitle?: string;
  geography?: string;
  domain: 'education' | 'justice' | 'economy' | 'cross-system';
  /** Default 4-slide sequence if no persona variation is specified */
  slides: [
    StoryboardSlideHumanContext,
    StoryboardSlideIntersections,
    StoryboardSlideRootCauses,
    StoryboardSlideCivicAction
  ];
  /** Optional persona-tailored slide decks */
  personaVariations?: Partial<
    Record<
      AudiencePersona,
      [
        StoryboardSlideHumanContext,
        StoryboardSlideIntersections,
        StoryboardSlideRootCauses,
        StoryboardSlideCivicAction
      ]
    >
  >;
  citations?: Array<{
    source: string;
    vintage: string;
    metricName: string;
    url?: string;
  }>;
}
