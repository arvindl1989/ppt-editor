---
name: kone-milestone-slide
description: Turn an internal announcement email (a launch, migration, programme win, transformation milestone) into a single on-brand KONE 1280×720 slide. Use when someone pastes an email or Teams post and wants "one slide I can share" rather than a deck.
license: Proprietary — KONE brand assets. Internal / authorized use only.
---

# KONE Milestone Slide — skill

One email in, one slide out. This is the recognition/status slide that does not exist in the master deck: a headline claim, a band of proof numbers, the scope behind them, what happens next, and who did it.

Requires the `kone-design` skill for tokens, fonts and assets. Start from `MilestoneSlide.dc.html` in this folder.

## When to use

Use it when the source is an announcement — something finished, and the audience needs the result plus credit. Signals in the text: a completion claim ("now live", "100% complete"), a duration ("in 6 weeks"), counts of people or units, a thank-you list, and a "what's next" section.

Do **not** use it for a proposal, a decision request, or anything needing an argument across several beats. Those are decks — go to `templates/kone-deck/ARCHETYPES.md`.

## Reading the email

Pull six things, in this order. If one is missing, the slide still works; if three are missing, it is not a milestone announcement.

1. **The claim** — what changed, compressed to one line under about 55 characters. Prefer the from→to shape with the duration in it: "From Monday.com to ServiceNow in six weeks". This becomes the 42px headline.
2. **The proof numbers** — at most five, each a bare integer with a short label. Duration, people, units, geographies, and one number that is deliberately zero (disruption, downtime, escalations). Zero is the strongest number on the slide; render it in black while the rest are blue, so it reads as a different kind of claim.
3. **Completion states** — the binary facts ("MVP pilot-tested and live", "100% transition completed"). Two ticks, top right. Never more than three.
4. **The scope names** — the actual units, markets or teams behind one of the numbers. These belong *attached to that number*, not floating on their own. If the list does not match a number exactly, cut it or fix the number.
5. **What's next** — three items maximum, each with its owner or date where the email gives one. Present tense, no hedging.
6. **The credits** — the names, verbatim and in the order given. Add group names ("and the Hub specialists") only where the email names a group.

Everything the email says that does not land in one of those six is context, and context does not go on a milestone slide.

## Geometry — 1280 × 720, 45px grid

```
logo                 assets/logo/kone-logo.svg, top 45, right 46, h 31
eyebrow              left 45, top 47, KONE Information, 12px, uppercase, .08em, blue
headline             left 45, top 82, width 790, Inter 400, 42px/1.1, -.02em, black
lede                 left 45, top 186, width 700, 17px/1.5, black
completion ticks     left 880, top 186, width 355, column, gap 14
                     · 20px blue circle, white ✓ 12px · label 16px/1.35 black
stat band (sand)     left 0, top 276, width 1280, height 196, --sand
stat row             left 45, top 276, width 1190, height 152, flex, align center, gap 40
                     · number KONE Information 62px/1, blue (the zero-stat: black)
                     · label  KONE Information 12px, uppercase, .06em, black, margin-top 12
scope row            left 45, top 424, width 1190, baseline flex, gap 16,
                     padding-top 14, border-top 1px --hairline-strong
                     · label KONE Information 11px uppercase blue
                     · names KONE Information 13px, .03em, black
what's next          left 45,  top 520, width 700  — blue uppercase head, hairline, <ul list-style:disc>
credits              left 880, top 520, width 355  — same head treatment, 16px/1.45 body
footer               left 45, bottom 43, KONE Information 11px uppercase — classification
```

Numbers stay one size. `100+`, `3+3` and `6` are all 62px — never shrink the `+` or a suffix into a smaller span, it makes the row look broken rather than typeset.

## Rules carried from the brand

- Left-aligned throughout. Logo top-right, always.
- Sand is the only secondary colour on this slide. Blue carries the numbers, black carries the text.
- **Never grey type.** No `--black-60`, no opacity for de-emphasis. Separate by size, weight and position.
- Real bullet markers: `<ul style="list-style:disc">`, marker in blue via `color` on the `<li>`, text in a black `<span>`.
- Inter is never blue. KONE Information is the only blue text.
- No emoji. The `✓` in the tick badges is a glyph, not an emoji, and is the only symbol on the slide.

## Failure modes

- **Slide collapses below 1280px.** If the slide sits in a `display:flex` wrapper, give the `<section>` `flex:0 0 auto` — `flex-shrink` defaults to 1 and silently clips the right third, taking the ticks and credits with it.
- **Footer collision.** The two bottom columns start at 520 and must clear the footer line at ~677. Three "what's next" items is the ceiling; a fourth pushes into it.
- **Orphan scope list.** A long list of codes floating in white space reads as a mistake. Anchor it: inside the sand band, under a hairline, with a label. Or cut it.
- **Redundant scope list.** If the list restates counts already in the band ("3 regions" plus the three region names), it is saying nothing twice. Keep only the list that names something the numbers cannot.
- **Padding the band.** Four strong numbers beat five where one is filler. Empty cells are better than invented metrics.

## Worked example

Source: a Marketing Hub email announcing a Monday.com → ServiceNow migration.

| Extracted | Rendered as |
|---|---|
| "In just 6 weeks… migrated its entire Request Management framework" | headline + the `6` stat |
| "MVP pilot-tested and is now live" / "100% transition completed" | the two ticks |
| "100+ users across 12 frontlines", "3 regions and 3 global teams" | `100+`, `12`, `3+3` |
| "Zero business disruption" | the black `0` |
| KSEA, KMTA, KANZ, KEI, EEM, DACH, GIN, Nordics, FBL, ITIB, USCA, USMX | scope row under the band — 12 names, matching the `12` |
| "full data continuity… historical tickets, files, feedback" | the lede |
| hypercare / Power BI Q2 / demo 21 April | what's next, three items |
| Arvind, Suresh Kumar, Rupesh, Vimendra, Chandra, Teja, Jaakko, Golda | credits, verbatim, plus "and the Hub specialists" |

Note what was cut: the regional and global-team names (already counted in the band), the closing paragraph about speed and accountability (rhetoric, not fact), and the team-line "KBS + Global Marketing + Frontlines + Business Partner", which was folded into the lede.

## Using it in Claude Code

Place this folder at `~/.claude/skills/kone-milestone-slide/` or `<repo>/.claude/skills/kone-milestone-slide/` alongside the `kone-design` skill. Copy `MilestoneSlide.dc.html` as the starting file, keep `ds-base.js` next to it, and point the `base` line in `ds-base.js` at wherever the KONE design system tree lives relative to the page.
