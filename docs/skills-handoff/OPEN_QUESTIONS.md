# What I could not decide alone

## 1. Do the baked type blocks go, or get blessed?

83 regions, 29% of the library. Removing them makes the brand
the single authority and changes 25 slides. Keeping them
means `BRAND_MODE.md` is advisory for a third of the deck, which makes
the contract layer a half-truth.

## 2. How should a display size be expressed?

The divider wants a 300px numeral and a 56px title. `TYPE_SCALE` has
`display` at 44px. Options: more roles (`divider_numeral`,
`divider_title`, and what else?), a size override on the contract, or a
per-archetype scale factor. The first is verbose, the second reopens the
hole, the third is magic.

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
