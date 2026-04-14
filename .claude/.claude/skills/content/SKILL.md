---
name: content
description: >
  Use when writing or refining landing page copy, marketing content, product descriptions,
  defining brand voice, crafting CTAs, planning keyword strategy, optimising on-page SEO,
  or producing technical SEO specifications (structured data, canonical URLs, sitemaps).
---

## Working Protocol

When given a copy or SEO task:

1. **Ground in the persona**: Read the relevant persona(s) in `PRD.md`. Identify their job-to-be-done, their language (words they use), and their objections. Write for them, not for a generic user.
2. **Read `CONTENT_STRATEGY.md`**: Check existing brand voice rules, active keyword targets, and the CTA library before introducing anything new. Consistency beats novelty.
3. **Classify the task** — pick the right mode before writing:
   - **Conversion copy** (landing pages, hero sections, email subject lines): use a copywriting framework (see below)
   - **SEO content** (blog posts, help articles, feature pages): use the content hierarchy and keyword framework
   - **Technical SEO spec** (structured data, meta tags, canonicals): produce a spec only — delegate implementation
4. **Apply the right framework** (see Copywriting Frameworks below).
5. **Deliver variants for high-stakes elements**: always provide 2–3 options for primary headlines and primary CTAs. Body copy and meta descriptions need one polished version only.
6. **Run the On-Page SEO Checklist** (see below) before marking any page copy task complete.
7. **Update `CONTENT_STRATEGY.md`**: log new keyword targets, copy decisions, voice notes, and CTAs added during the task.

## Copywriting Frameworks

Choose the framework that matches the audience's awareness level. Never mix frameworks within a single page section.

### AIDA — Awareness → Interest → Desire → Action

Use for: cold-audience landing pages, product launch announcements, paid ad destinations.

```
Attention: Interrupt the scroll with a bold claim or provocative question.
           Match the exact language the persona uses to describe their problem.
Interest:  Explain why this problem is harder/more expensive than they thought.
           Use specific numbers and concrete outcomes, not adjectives.
Desire:    Show the transformation. "Before: X. After: Y." Use social proof here.
Action:    Single, clear CTA. State what happens next ("Start your free trial —
           no credit card required").
```

### PAS — Problem → Agitate → Solution

Use for: problem-aware audiences, pricing pages, comparison pages, cold outreach.

```
Problem:   Name the pain precisely. The reader should think "that's exactly it."
Agitate:   Deepen the pain — what does it cost them? Time, money, reputation?
           Avoid manufactured urgency; use real consequences.
Solution:  Introduce the product as the relief. Lead with the outcome, not
           the feature. "You get X" before "We built Y".
```

### FAB — Feature → Advantage → Benefit

Use for: feature pages, product descriptions, onboarding flows, release notes.

```
Feature:   What it does ("real-time collaboration")
Advantage: Why that matters vs. the alternative ("no emailing files back and forth")
Benefit:   The outcome the user cares about ("ship 2× faster without the version chaos")
```

### Value Proposition Hierarchy

Every page has one primary value prop. Everything else supports it or is cut.

```
Level 1 — Headline (H1): the single most compelling benefit. Not a tagline.
           Formula A: [Outcome] for [Persona] [without pain/time/cost]
           Formula B: [Verb] [specific result] in [timeframe]
Level 2 — Sub-headline: expand the headline. Add specificity or handle
           the strongest objection.
Level 3 — Supporting copy: features translated to benefits (use FAB).
Level 4 — Social proof: numbers, logos, testimonials — placed immediately
           after the primary value prop, not buried below the fold.
Level 5 — CTA: action-oriented, specific, low-friction.
```

## Brand Voice & Tone Framework

### Voice Dimensions

Voice is constant. Tone shifts by context.

| Dimension | Spectrum | Default setting |
|-----------|----------|-----------------|
| Formality | Formal ←→ Casual | [Fill in when brand is defined] |
| Energy | Subdued ←→ Energetic | [Fill in when brand is defined] |
| Personality | Corporate ←→ Human | [Fill in when brand is defined] |
| Authority | Humble ←→ Expert | [Fill in when brand is defined] |

### Tone-by-Context Matrix

| Context | Tone adjustment | Example |
|---------|----------------|---------|
| Error messages | Calm, never apologetic — explain what happened and what to do | "That email is already in use. Sign in instead, or reset your password." |
| Success / confirmations | Warm, brief, forward-looking | "You're in. Here's what to do next →" |
| Marketing headlines | Confident, benefit-led, specific | "Ship twice as fast. No extra headcount." |
| Onboarding | Encouraging, step-by-step, no jargon | "Let's set up your first project. It takes about 2 minutes." |
| Pricing page | Direct, no weasel words, objection-handling | "Cancel any time. No questions." |
| Empty states | Helpful, not cutesy — tell the user what to do | "No projects yet. Create your first one →" |

### Forbidden Phrases

Never write these — they are vague, overused, or erode trust:

- "World-class" / "best-in-class" / "industry-leading"
- "Seamless" / "frictionless" / "intuitive" (show it, do not claim it)
- "Leverage" / "synergy" / "ecosystem" (corporate filler)
- "We're excited to announce" (reader does not care about your excitement)
- "Simply" / "just" / "easily" (patronising if the task is not simple)
- "Please note that" / "It is important that" (padding)
- Any claim without a number or proof point: "significantly faster", "many customers"

### Power Words (use deliberately, not excessively)

Specificity words: `exactly`, `proven`, `in [X] minutes`, `[N]% of customers`
Action words: `ship`, `cut`, `eliminate`, `unlock`, `automate`
Trust words: `guaranteed`, `no credit card`, `cancel any time`, `used by [specific number]`

## SEO Strategy

### Keyword Intent Classification

Map every keyword to exactly one intent before targeting it. A page can only serve one intent well.

| Intent | What the user wants | Content type that ranks |
|--------|--------------------|-----------------------|
| **Informational** | Learn something | Blog post, guide, explainer |
| **Navigational** | Find a specific site/page | Homepage, brand pages |
| **Commercial investigation** | Compare options before buying | Comparison page, feature page, review |
| **Transactional** | Take action now (buy, sign up, download) | Landing page, pricing page |

### Keyword-to-Page Mapping Rules

- One primary keyword per page. Multiple pages targeting the same keyword create keyword cannibalization — avoid it.
- Supporting keywords (secondary, LSI) appear naturally in subheadings and body copy — do not force them.
- Map keywords in `CONTENT_STRATEGY.md` before writing content. If a keyword is already mapped to another page, do not add a competing page — update or improve the existing one.

### Topical Authority Model

Search engines reward sites that cover a topic deeply, not broadly.

```
Pillar page: broad topic ("Project Management Software")
  └── Cluster page: subtopic ("Agile vs Waterfall Project Management")
  └── Cluster page: subtopic ("How to Set Up a Project Timeline")
  └── Cluster page: subtopic ("Project Management for Remote Teams")

Rules:
- Every cluster page links back to its pillar page
- The pillar page links to all cluster pages
- Cluster pages cross-link to each other when relevant
- Do not create cluster pages before the pillar page exists
```

## On-Page SEO Checklist

Run this before marking any page copy task complete:

- [ ] **Title tag**: 50–60 characters. Primary keyword near the front. Format: `[Primary Keyword] — [Brand Name]` or `[Benefit] | [Brand Name]`. Do not stuff keywords.
- [ ] **Meta description**: 150–160 characters. Include the primary keyword naturally. Include a CTA or benefit statement. This is copy, not a keyword list.
- [ ] **H1**: One per page. Contains primary keyword. Matches or closely mirrors the title tag intent (not identical wording).
- [ ] **H2–H6**: Logical hierarchy. H2s are major sections. H3s are subsections of H2s. Never skip levels. Subheadings contain secondary keywords naturally — do not force them.
- [ ] **URL slug**: lowercase, hyphens (not underscores), primary keyword included, no stop words (`the`, `a`, `an`, `and`), no dates (they go stale). Example: `/project-management-software` not `/our-amazing-project-management-software-tool-2024`.
- [ ] **First 100 words**: primary keyword appears naturally in the first paragraph.
- [ ] **Internal links**: at least 2 internal links to relevant pages; anchor text is descriptive (not "click here").
- [ ] **Image alt text**: describes the image content and includes the keyword where natural. Decorative images use `alt=""`.
- [ ] **Word count**: informational content ≥ 800 words to cover the topic; landing pages can be shorter if the value prop is clear and complete.
- [ ] **Duplicate content check**: confirm no other page targets the same primary keyword.

## Technical SEO Specifications

Produce specs; delegate implementation to front-end or back-end.

### Meta Tags Spec Format

```
Page: [page name / route]
Title tag: [exact text — 50–60 characters]
Meta description: [exact text — 150–160 characters]
Canonical URL: [full URL — use self-referencing canonical on all pages]
robots: [index, follow | noindex, nofollow — specify only if non-default]
og:title: [Open Graph title for social sharing]
og:description: [Open Graph description]
og:image: [path to social image — 1200×630px]
```

### JSON-LD Structured Data Templates

**Organization** (homepage):
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "[Company Name]",
  "url": "[https://example.com]",
  "logo": "[https://example.com/logo.png]",
  "sameAs": ["[Twitter URL]", "[LinkedIn URL]"]
}
```

**WebSite** (homepage — enables sitelinks search box):
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "[Site Name]",
  "url": "[https://example.com]"
}
```

**Article** (blog posts):
```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "[Article title — matches H1]",
  "datePublished": "[ISO 8601 date]",
  "dateModified": "[ISO 8601 date]",
  "author": { "@type": "Person", "name": "[Author Name]" },
  "publisher": { "@type": "Organization", "name": "[Brand]", "logo": { "@type": "ImageObject", "url": "[logo URL]" } },
  "image": "[hero image URL]",
  "description": "[meta description text]"
}
```

**FAQPage** (FAQ sections):
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "[Question text — exact match to H3 on page]",
      "acceptedAnswer": { "@type": "Answer", "text": "[Answer text — first 300 chars of answer]" }
    }
  ]
}
```

**BreadcrumbList** (all pages except homepage):
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "[https://example.com]" },
    { "@type": "ListItem", "position": 2, "name": "[Section]", "item": "[https://example.com/section]" },
    { "@type": "ListItem", "position": 3, "name": "[Current Page]" }
  ]
}
```

### Canonical URL Rules

- Self-referencing canonical on every page — no exceptions.
- Paginated content: canonical on page 1 pointing to itself; pages 2+ self-referencing.
- Faceted navigation (filtered product listings): canonical to the unfiltered base URL unless the filtered view has significant search demand.
- HTTP and HTTPS, www and non-www must all redirect to one canonical version — specify the chosen version in `CONTENT_STRATEGY.md`.

### Hreflang Spec (multi-locale only)

```
Locale: [e.g., en-US]
URL:    [https://example.com/en-us/...]
Hreflang: en-US

x-default: [https://example.com/] — points to language-selection page or primary locale
```

## CTA Hierarchy

Every page has at most three CTA levels. More than three CTAs on a page means the page has no clear goal.

| Level | Purpose | Placement | Style |
|-------|---------|-----------|-------|
| **Primary** | The one action you want the user to take | Above the fold; repeated at page bottom | Full button, high contrast |
| **Secondary** | Alternative path for users not ready for primary | Below primary CTA | Ghost button or text link |
| **Tertiary** | Navigation or supplementary action | Mid-page or footer | Text link |

### CTA Copy Rules

- Lead with a verb: "Start", "Get", "Try", "See", "Download" — not "Submit", "Click", "Enter"
- Be specific: "Start my free trial" beats "Get started"
- State what happens next: "Start my free trial — cancel any time" removes the primary objection inline
- Match the CTA copy to the stage of awareness: cold audiences need lower-commitment CTAs ("See how it works") vs. warm audiences ("Start free trial")

### A/B Variant Format

```markdown
## [Page name] — Copy Variants

### Primary Headline

**Variant A** (benefit-led):
[Headline text]

**Variant B** (outcome-led):
[Headline text]

**Variant C** (problem-led):
[Headline text]

**Recommendation**: Variant [X] because [one-sentence reason based on persona awareness level].

### Primary CTA

**Variant A**: [CTA text]
**Variant B**: [CTA text]

**Recommendation**: [X] because [reason].
```

## CONTENT_STRATEGY.md Update Format

When completing a task, append any new decisions to the relevant section in `docs/content/CONTENT_STRATEGY.md`:

**New keyword target**:
```markdown
| [keyword] | [intent] | [page mapped to] | [monthly search volume if known] | [date added] |
```

**New CTA added to library**:
```markdown
| [CTA text] | [page / context] | [level: primary/secondary/tertiary] | [date added] |
```

**Voice note** (write to Brand Voice section):
```markdown
- [Rule or example discovered during this task — one line]
```

## Anti-Patterns

- **Keyword stuffing**: using a keyword 8 times in 300 words does not help rankings — it reads as spam and tanks click-through rate.
- **Writing for bots, not humans**: if a sentence would sound unnatural read aloud, rewrite it.
- **Vague CTAs**: "Learn more", "Click here", "Submit" — they say nothing.
- **Passive headlines**: "Your productivity will be improved" → "Double your output". Passive voice buries the benefit.
- **Mismatched search intent**: writing a listicle for a transactional keyword, or a salesy landing page for an informational query.
- **Duplicate title tags**: every page must have a unique title tag.
- **Meta descriptions as keyword lists**: write a sentence, not a keyword dump.
- **Burying the value prop**: if the user has to scroll to understand what the product does, the page is broken.
- **Social proof without specifics**: "Thousands of companies trust us" → "14,000 teams ship faster with [Product]".
