# The reported slide, before and after

`renders/divider-2.jpg` is the slide the report came in about, on the
pink field. Everything below is measured off the renders.

## Before

| | ink | declared |
| --- | --- | --- |
| numeral `02` | 210 x 142px, black | 190px Inter |
| eyebrow `Boundaries` | 11px x-height, sentence case | 13px Inter |
| title | 45px cap height | 46px Inter |

Four faults, only one of them a font size:

1. **The eyebrow was body copy.** 11px of x-height in sentence case is
   the treatment a paragraph gets. This is the one that read as
   "whack" -- a section marker looking like a stray sentence.
2. **Nothing separated the eyebrow from the title.** 26px between the
   eyebrow's baseline and the title's cap, on a slide with 460px of
   empty field below them.
3. **The numeral was half the size it should be.** 142px of cap height
   from a 190px declaration, against a spec asking for 300px.
4. **The block rode high.** Ink spanned y=258..400 on a 720px canvas;
   centre at 329 against a canvas centre of 360.

The numeral was **not** clipped, which is worth saying because it looks
like it might be -- its ink stopped at y=400 inside a box running to
y=510. The flat edge under the `2` is the glyph.

## After

All three slots now resolve through the brand and carry no type of
their own. Measured on the same render:

| | ink | role | against target |
| --- | --- | --- | --- |
| numeral | 212px tall, centred on y=360 | `section_numeral` | y=360 exactly |
| eyebrow | 10px x-height, CAPS, blue | `eyebrow` | 12px KONE Information |
| title | 54px, one line | `divider_title` | 56px |
| eyebrow to title | 28px | — | 26px |

Across all four fields the numeral's ink centre measures 360, 360, 360,
361. On the blue field every element reverses to white, which is a
thing that had never worked for a role-based region before.

## Where each number comes from

```json
{
  "spec_says": "INTERNAL_25.md 05: 300px blue numeral at left:38 top:150. Section label and 56px title at x:620.",
  "brand_says": "BRAND_MODE.md types the numeral `figure`: 200px, black, 'black on every secondary field'. The two documents disagree on both size and colour.",
  "contract_says": "number (a few words, set very large) · eyebrow? (2-5 words, uppercase) · title",
  "renders_as": [
    {
      "slot": "number",
      "role": "section_numeral",
      "box": [
        45,
        182,
        374,
        340
      ],
      "type": null
    },
    {
      "slot": "eyebrow",
      "role": "eyebrow",
      "box": [
        453,
        317,
        578,
        120
      ],
      "type": null
    },
    {
      "slot": "title",
      "role": "divider_title",
      "box": [
        453,
        343,
        760,
        160
      ],
      "type": null
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
        "top": 255,
        "bottom": 466,
        "ink_height": 212,
        "left": 61,
        "right": 375
      }
    ],
    "text_column": [
      {
        "top": 320,
        "bottom": 329,
        "ink_height": 10,
        "left": 453,
        "right": 511
      },
      {
        "top": 357,
        "bottom": 410,
        "ink_height": 54,
        "left": 453,
        "right": 1080
      }
    ]
  }
}
```
