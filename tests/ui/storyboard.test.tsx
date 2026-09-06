import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  StoryboardPresenter,
  StoryboardModal,
  StoryboardStory,
} from '../../ui/storyboard';

const mockStory: StoryboardStory = {
  id: 'test-story-literacy',
  topic: 'Third-Grade Literacy & Systemic Drivers',
  title: 'The Literacy Gap in Memphis',
  subtitle: 'How early education disinvestment compounds over time',
  geography: 'Memphis-Shelby County',
  domain: 'education',
  slides: [
    {
      slideNumber: 1,
      type: 'human_context',
      headline: '3 in 4 Third Graders Are Not Reading on Grade Level',
      narrative: 'Across Memphis-Shelby County Schools, early literacy is the first public gate.',
      primaryStat: {
        label: '3rd Grade ELA Proficiency',
        value: '23.4%',
        benchmarkLabel: 'Tennessee State Average',
        benchmarkValue: '38.9%',
      },
      humanAnchorQuote: 'If a child cannot read by third grade, the whole curriculum becomes an uphill battle.',
      humanAnchorAttribution: 'Local Educator',
    },
    {
      slideNumber: 2,
      type: 'intersections',
      headline: 'Early Literacy Intersects with Youth Justice and Housing',
      narrative: 'Reading difficulties in early grades correlate with higher rates of later exclusionary discipline.',
      crossDomainMetrics: [
        { domain: 'education', label: 'Suspension Share', value: '85.2%', contextNote: 'Black students' },
        { domain: 'justice', label: 'Juvenile Court Referrals', value: '4.1x', contextNote: 'Higher in underfunded ZIPs' },
        { domain: 'economy', label: 'Young Children Not in School', value: '58.5%', contextNote: 'Ages 3–4 Census ACS' },
      ],
      intersectionTakeaway: 'School failure is systematically linked to neighborhood disinvestment.',
    },
    {
      slideNumber: 3,
      type: 'root_causes',
      headline: 'Root Causes: Funding Formulas and Tax Abatements',
      narrative: 'Tennessee funding mechanisms and local tax abatements impact school resources.',
      structuralDrivers: [
        { title: 'TISA Formula Base', description: 'Undercounts concentrated urban poverty.', tag: 'State' },
        { title: 'Local Tax Abatements', description: 'PILOT programs divert revenue.', tag: 'Local' },
      ],
      fundingContext: 'MSCS receives less local revenue per pupil than suburban municipal peers.',
    },
    {
      slideNumber: 4,
      type: 'civic_action',
      headline: 'What the Community Can Demand Now',
      narrative: 'Elected officials have the statutory authority to address early learning and discipline.',
      policyAsks: [
        { tier: 'Immediate Budget Ask', ask: 'Fund 500 new high-quality Pre-K seats.', targetOfficial: 'County Commission' },
        { tier: 'Structural Policy Reform', ask: 'End exclusionary out-of-school suspensions for grades K-5.', targetOfficial: 'MSCS Board' },
      ],
      responsibleBody: {
        name: 'MSCS Board of Managers',
        meetingSchedule: 'Last Tuesday of every month at 5:30 PM',
        location: '160 S. Hollywood St., Auditorium',
        publicCommentSignupUrl: 'https://www.scsk12.org/board',
      },
      talkingPoints: [
        'Third-grade reading proficiency in MSCS is 23.4% versus 38.9% statewide.',
        'Over 58% of children ages 3-4 are not enrolled in pre-K.',
        'We demand dedicated county funding for early learning seats.',
      ],
    },
  ],
  personaVariations: {
    policymaker: [
      {
        slideNumber: 1,
        type: 'human_context',
        headline: 'MSCS Third-Grade Literacy Lags State Benchmark by 15.5 Points',
        narrative: 'Baseline academic metrics under the TDOE TCAP assessment indicate persistent proficiency shortfalls.',
        primaryStat: {
          label: '3rd Grade ELA Proficiency',
          value: '23.4%',
          benchmarkLabel: 'TDOE Statewide Benchmark',
          benchmarkValue: '38.9%',
        },
      },
      {
        slideNumber: 2,
        type: 'intersections',
        headline: 'Fiscal & Jurisdictional Intersections',
        narrative: 'Academic deficits correlate with downstream fiscal pressures on juvenile justice and social services.',
        crossDomainMetrics: [
          { domain: 'education', label: 'Suspension Rate', value: '85.2%' },
          { domain: 'justice', label: 'Court Contact Multiplier', value: '4.1x' },
          { domain: 'economy', label: 'Pre-K Unmet Need', value: '58.5%' },
        ],
      },
      {
        slideNumber: 3,
        type: 'root_causes',
        headline: 'Fiscal Drivers: TISA Allocation & Local Capacity',
        narrative: 'Statutory funding mechanisms under T.C.A. Title 49 require targeted local matching.',
        structuralDrivers: [
          { title: 'TISA Direct Weighting', description: 'Direct certified poverty weighting threshold.', tag: 'Statute' },
        ],
      },
      {
        slideNumber: 4,
        type: 'civic_action',
        headline: 'Policy Recommendations & Oversight Actions',
        narrative: 'Statutory authorities available to the Board of Managers and Shelby County Commission.',
        policyAsks: [
          { tier: 'Statutory Lever', ask: 'Reallocate Title I / local capital surplus to early literacy interventions.' },
        ],
        responsibleBody: {
          name: 'Shelby County Commission',
          meetingSchedule: '1st and 3rd Mondays at 1:30 PM',
        },
        talkingPoints: [
          'TISA direct certification allocation requires local supplemental match.',
        ],
      },
    ],
  },
  citations: [
    { metricName: '3rd Grade ELA', source: 'TDOE Assessment File', vintage: '2024-25' },
  ],
};

describe('StoryboardPresenter', () => {
  it('renders Slide 1 (Human Context) on initial mount', () => {
    render(<StoryboardPresenter story={mockStory} />);

    expect(screen.getByText('The Literacy Gap in Memphis')).toBeDefined();
    expect(screen.getByText('3 in 4 Third Graders Are Not Reading on Grade Level')).toBeDefined();
    expect(screen.getByText('23.4%')).toBeDefined();
    expect(screen.getByText('Tennessee State Average')).toBeDefined();
    expect(screen.getByText('38.9%')).toBeDefined();
  });

  it('navigates through slides using Next and Previous buttons', () => {
    render(<StoryboardPresenter story={mockStory} />);

    const nextButton = screen.getByRole('button', { name: /next slide/i });
    const prevButton = screen.getByRole('button', { name: /previous slide/i });

    // Initially at Slide 1, Prev is disabled
    expect(prevButton.hasAttribute('disabled')).toBe(true);

    // Click Next -> Slide 2 (Intersections)
    fireEvent.click(nextButton);
    expect(screen.getByText('Slide 2 of 4 • Cross-Domain Intersections')).toBeDefined();
    expect(screen.getByText('Early Literacy Intersects with Youth Justice and Housing')).toBeDefined();
    expect(screen.getByText('85.2%')).toBeDefined();

    // Click Next -> Slide 3 (Root Causes)
    fireEvent.click(nextButton);
    expect(screen.getByText('Slide 3 of 4 • Root Causes & Structural Drivers')).toBeDefined();
    expect(screen.getByText('Root Causes: Funding Formulas and Tax Abatements')).toBeDefined();

    // Click Next -> Slide 4 (Civic Action)
    fireEvent.click(nextButton);
    expect(screen.getByText('Slide 4 of 4 • Direct Civic Action & Advocacy')).toBeDefined();
    expect(screen.getByText('What the Community Can Demand Now')).toBeDefined();
    expect(screen.getByText('3-Minute Public Comment Script')).toBeDefined();
    expect(nextButton.hasAttribute('disabled')).toBe(true);

    // Click Prev -> Slide 3
    fireEvent.click(prevButton);
    expect(screen.getByText('Root Causes: Funding Formulas and Tax Abatements')).toBeDefined();
  });

  it('switches persona and adapts slide content dynamically', () => {
    render(<StoryboardPresenter story={mockStory} />);

    // Click Policymaker persona
    const policymakerTab = screen.getByText('Policymaker');
    fireEvent.click(policymakerTab);

    expect(
      screen.getByText('MSCS Third-Grade Literacy Lags State Benchmark by 15.5 Points')
    ).toBeDefined();
  });
});

describe('StoryboardModal', () => {
  it('renders modal when open and closes on Escape or close button', () => {
    const handleClose = vi.fn();
    const { rerender } = render(
      <StoryboardModal isOpen={true} onClose={handleClose} story={mockStory} />
    );

    expect(screen.getByRole('dialog')).toBeDefined();

    // Close button
    const closeBtn = screen.getByRole('button', { name: /close storyboard/i });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);

    // Escape key
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(2);

    // When isOpen is false, nothing is rendered
    rerender(<StoryboardModal isOpen={false} onClose={handleClose} story={mockStory} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
