# The reported slide, measured

`renders/divider-2.jpg` is the slide the report came in about. What
follows is measured off that image, not read off the spec.

## What a reader sees

| | ink | declared | the spec asks for |
| --- | --- | --- | --- |
| numeral `02` | 210 x 142px, black | 190px Inter | **300px, KONE Blue** |
| eyebrow `Boundaries` | 11px x-height, sentence case | 13px Inter | a section label, uppercase |
| title | 45px cap height | 46px Inter | **56px** |

Four separate faults, and only one of them is a font size:

1. **The numeral is black.** The spec says KONE Blue and the contract
   calls it a display figure. Rendered in the same ink as the title, at
   142px of cap height against the title's 45px, it does not read as a
   section index -- it reads as a large dark shape the eye has to get
   past.
2. **The eyebrow is body copy.** 11px of x-height in sentence case is
   the same treatment a paragraph gets. The brand's label role is 12px
   KONE Information in caps. This is the one that reads as "whack": a
   section marker looking like a stray sentence.
3. **Nothing separates the eyebrow from the title.** 26px between the
   eyebrow's baseline and the title's cap, on a slide with 460px of
   empty field below them. The pair reads as one lump.
4. **The block rides high.** The ink spans y=258..400 on a 720px
   canvas; its centre is at 329 against a canvas centre of 360. Not
   enough to look deliberate, enough to look unplaced.

The numeral is NOT clipped, which is worth saying because it looks like
it might be -- its ink stops at y=400 inside a box that runs to y=510.
The flat edge under the `2` is the glyph.

## Where each number comes from

```json
{
  "spec_says": "INTERNAL_25.md 05: 300px blue numeral at left:38 top:150. Section label and 56px title at x:620.",
  "contract_says": "number (a few words, set very large) · eyebrow? (2-5 words, uppercase) · title",
  "renders_as": [
    {
      "slot": "number",
      "box": [
        45,
        210,
        374,
        300
      ],
      "type": {
        "kind": "text",
        "px": 190,
        "font": "Inter",
        "color": "141414",
        "caps": false,
        "align": "l"
      }
    },
    {
      "slot": "eyebrow",
      "box": [
        453,
        276,
        578,
        120
      ],
      "type": {
        "kind": "text",
        "px": 13,
        "font": "Inter",
        "color": "141414",
        "caps": false,
        "align": "l"
      }
    },
    {
      "slot": "title",
      "box": [
        453,
        304,
        578,
        150
      ],
      "type": {
        "kind": "text",
        "px": 46,
        "font": "Inter",
        "color": "141414",
        "caps": false,
        "align": "l"
      }
    }
  ],
  "measured_from_the_render": {
    "canvas": [
      1281,
      720
    ],
    "field": "#FFCDD8",
    "numeral_column": [
      {
        "top": 258,
        "bottom": 400,
        "ink_height": 143,
        "left": 56,
        "right": 266
      }
    ],
    "text_column": [
      {
        "top": 278,
        "bottom": 288,
        "ink_height": 11,
        "left": 454,
        "right": 521
      },
      {
        "top": 314,
        "bottom": 358,
        "ink_height": 45,
        "left": 454,
        "right": 968
      }
    ]
  }
}
```
