# Dashboard design notes

Written before the code, then reviewed against the brief. The brief: a portfolio audit that makes one idea land fast, that five reasonable definitions of one metric disagree, and lets a reader check it.

## Plan

**Colour** (light / dark)
- Sheet `#fcfcfb` / `#1a1a19`: the page and every chart sit on the same plane. No cards.
- Ink `#0b0b0b` / `#f0efec`, secondary `#52514e` / `#c3c2b7`, muted `#6b6a65` / `#a3a299`.
- Governed blue `#2a78d6` / `#3987e5`: reserved for the governed definition on every metric.
- Other four definitions take the next four slots of the validated categorical order: orange, aqua, yellow, magenta.
- Severity uses the fixed status palette with an icon and a word, never colour alone.

**Type.** One sans family (Inter, falling back to the system UI font). Weight and size do the work: 56px headline, 24px statement headings, proportional figures for the big number, tabular figures only in table columns.

**Layout.** Left aligned, one column up to 1080px, sections divided by hairlines. One sticky row of filters (metric, month, theme) scopes everything below it.

```
Headline + one sentence + data line
[ Revenue | Active customers | Order value ]   Month [Nov 2011]   [Dark mode]
-------------------------------------------------------------------
Statement heading with the real numbers
 79%     o  Gross sales            £251K
 big     o  Net clean (governed)   £249K   <- five dots on one axis
 figure  o  Identified customers   £140K
-------------------------------------------------------------------
Definitions | Trend | Decisions (flip strip + matrix) | Why they differ
Drift | Trust tests + duplicates by month | What a team does | Limits
```

**Principles**
1. Spend boldness once: the five-dot comparison under a very large gap figure. Everything else is quiet.
2. Headings state the finding, written from the data, so a new dataset gets true sentences.
3. Colour follows the entity. A definition keeps its colour on every chart; blue never means anything else.
4. Every chart has a table twin, keyboard access and a tooltip that is not the only way to read a value.

## Review against the usual defaults

Revisions made after the first draft:
- A row of identical KPI cards with a gradient accent was replaced by the five-dot comparison. Cards would have repeated the same number five times.
- Small uppercase eyebrow labels above headings were dropped. The headings carry the meaning.
- The first palette idea (cream paper, terracotta accent) was dropped. The subject is reconciliation, so a neutral sheet and one reserved blue fit better.
- Histogram and highlight bars use neutral ink and grey, so blue stays reserved for the governed definition.
- The flip calendar encodes with glyphs (≠, ~, =) plus fill, so it survives greyscale and colour blindness.

## Checks run

- `validate_palette.js` on the five categorical slots, light and dark: lightness band, chroma, CVD separation (worst adjacent ΔE 9.1 light, 8.4 dark), normal-vision separation (19.6, 19.3). Three light-mode colours are under 3:1 against the surface, so every line chart ships a legend, tooltips and a table view.
- Charts checked against the dataviz anti-patterns list: no dual axes, thin marks with a 2px surface ring, bars capped at 24px with rounded data ends, solid hairline grids, no number on every point, filters in one row above the charts.
- Interface checklist: body text 4.5:1 or better, visible focus rings, 44px controls, reduced motion respected, no emoji icons, no horizontal scroll at 390px.
- Rendered and inspected at 1200px and 390px, in light and dark.
