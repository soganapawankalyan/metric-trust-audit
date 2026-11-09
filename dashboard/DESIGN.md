# Dashboard design notes

Written before the code, then reviewed against the brief. The brief: a portfolio audit that makes one idea land fast, that one metric has several defensible definitions and that they disagree, and lets a reader check it.

## What changed in version 2

Version 1 was a competent report: a big gap number, a dot plot, a table, a trend, sections in one column. It looked like every other analytics page. Version 2 starts from the subject instead of the layout.

**The idea.** Revenue is not one number. It is five yes-or-no rules (include postage and fees, net off returns, drop repeated lines, drop lines on both sheets, drop guest orders). Every answer in the file is one of 32 combinations, and only five have a name. So the first thing on the page is a calculation tape, the way an accountant's adding machine prints it: one line per rule, each with a switch, a running total at the bottom. A reader who strikes a line through sees the number move, and the page tells them which named definition they just reproduced.

The 32 combinations are computed exactly, in the browser, from one small table of money by rule class (`rule_cells`, built in SQL). The five named combinations are checked against the SQL definitions in `tests/test_pipeline.py` and again in the browser.

## Plan

**Colour** (light / dark)
- Desk `#f3f4ef` / `#141615`, paper (tape and tooltips) `#fffefb` / `#1e211f`. A cool grey-green desk, not cream.
- Ink `#101210` / `#eef0ea`, secondary `#464a42` / `#c6c9bf`, muted `#62665b` / `#a0a496`.
- Governed blue `#2a78d6` / `#3987e5`: reserved for the governed definition on every metric.
- The other four definitions take the next four slots of the validated categorical order: orange, aqua, yellow, magenta. Re-validated on the new desk colour: worst adjacent CVD distance 9.1 light, 8.4 dark.
- Every coloured dot carries its definition id (R1 to R5, A1 to A5, V1 to V5), so identity never depends on colour, and every chart has a table view.

**Type.** One sans family for text. Amounts on the tape are monospaced with tabular figures, because that is what a ledger looks like and the digits line up. The tape total is the largest type on the page.

**Layout.** A control rail on the left (month stepper, chapter list, theme) that becomes a sticky top bar below 1100px. The work sits beside it, not under a header. Charts and tables sit on the page; the only raised object is the tape.

```
Rail            Masthead
Month  < >     --------------------------------------------
Chapters       The tape                 | All 32 ways (dots)
 The tape      [x] Add postage   +£6,326 | Your rules vs governed
 One ruler     [x] Net off ...   -£1,234 | what changes
 Over time     ...
 Decisions     Your revenue  £248,998   |
 ...           [R1][R2][R3][R4][R5]     |
```

**Principles**
1. Spend boldness once: the tape. Everything else is quiet.
2. Headings state the finding, written from the data, so a new dataset gets true sentences.
3. Colour follows the entity. A definition keeps its colour on every chart; blue never means anything else.
4. Every chart has a table twin, keyboard access and a tooltip that is not the only way to read a value.

## Review against the usual defaults

- Row of identical KPI cards with a gradient accent: not used. There are no cards; the tape is the one raised surface and it carries the content.
- Cream background with serif and terracotta: not used.
- Tracked all-caps labels above headings: not used.
- Numbered section markers: not used. The chapter list is names only.
- Hover and entrance animation on every block: none. Motion is limited to the switch knob and chart crosshair, both answering a click or pointer.

## Checks run

Light and dark at 1440, 1100, 1024, 820, 600, 390 and 360px with no horizontal overflow; keyboard reach for every switch, dot, cell and tab; all 24 months, all 32 rule combinations and all three metric tabs with no console errors; 44px touch targets on controls (the dots on the 32-way strip are small, so every combination is also reachable through the switches and named chips).
