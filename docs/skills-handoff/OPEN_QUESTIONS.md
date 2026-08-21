# What I could not decide alone

## 1. Do the baked type blocks go, or get blessed?

Answered for one archetype, still open for the rest. 62 regions
remain, 23% of the library. Removing them makes the brand the
single authority and changes 15 slides. Keeping them
means `BRAND_MODE.md` is advisory for a fifth of the deck, which makes
the contract layer a half-truth.

## 2. How should a display size be expressed?

**Answered: more roles, and it was cheaper than it looked.** The
objection was that the role list grows with every archetype wanting an
exception. In practice the divider needed two (`section_numeral`,
`divider_title`) and the brand's own type table already named both --
the scale had simply been transcribed incompletely. A size override on
a contract was the alternative and it is a baked block with a different
name. Re-open this if the next few archetypes each need their own.

## 2b. The numeral's colour -- NEW, and the one that needs a designer

`INTERNAL_25.md` says "300px blue numeral". `BRAND_MODE.md` types it
200px black and gives a reason: "black on every secondary field", which
matters because this slide ships on sand, pink, mint and light blue.
`brandmode.py` has held the spec's size with the brand's colour since
the scale was written. It is left black and reverses to white on blue.
Claude Design's review asked for blue, which contradicts both the field
rule and its own "Inter is never blue" line. Someone should just rule.

## 3. `eyebrow:body` in the handoff's own contract table

`EXTERNAL_25.md` types the divider's section label as `body`. That is
what put sentence-case body copy where a small-caps label belongs. Is
the table wrong, or is a divider's label genuinely not an eyebrow?

## 4. Is one model call defensible?

Splitting extraction from selection is the plan, and it doubles the
calls. With prompt caching the static guide is ~97% of the input and
identical every time, so the cost is close to flat — but it is two
places to go wrong instead of one. Worth it?

## 5. What should preflight refuse?

Today it reports everything and returns the file. Should anything be
fatal — type in an unapproved colour, say — or is a deck you can see the
faults in always better than no deck?
