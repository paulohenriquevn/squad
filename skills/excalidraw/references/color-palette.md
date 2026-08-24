# Color Palette — single source of truth

Every color in a generated diagram comes from this file. `SKILL.md` carries the *methodology*;
this file carries the *values*. To rebrand the skill, edit only this file — nothing in `SKILL.md`
names a color that is not defined here.

Surface is **GitHub dark**, matching `/marp-slide`'s `template-tech.md` so a diagram dropped into
a slide has no visible seam.

## Canvas

| Token | Hex | Use |
|---|---|---|
| `canvas` | `#0d1117` | `appState.viewBackgroundColor` — **always**, never `#ffffff` |
| `surface` | `#161b22` | raised panels, evidence artifact backgrounds |
| `surface-alt` | `#21262d` | a second panel level when two must be distinguished |
| `border` | `#30363d` | hairlines, table rules, inactive strokes |
| `muted` | `#484f58` | de-emphasized strokes, "not this path" |

## Semantic shape colors

Each purpose is a **fill + stroke pair**. Fill is deep and muted; stroke is bright and vivid — the
contrast is what makes a shape legible on a dark canvas. Never use a fill as a stroke.

| Purpose | Fill | Stroke | Reads as |
|---|---|---|---|
| Primary / neutral | `#1f2937` | `#58a6ff` | the default box; anything without a stronger meaning |
| Start / input | `#0f2f22` | `#3fb950` | where the flow enters |
| End / output / success | `#0f2f22` | `#2ea043` | where it lands, and it worked |
| Decision / gate | `#3a2e0b` | `#fbbf24` | a branch, a condition, a gate |
| AI / model / inference | `#2d1b45` | `#a855f7` | anything a model does |
| Storage / memory | `#0e2f38` | `#22d3ee` | database, cache, queue, disk |
| Error / refusal / kill | `#3d1418` | `#f85149` | the failure path, a refused operation |
| External / third-party | `#21262d` | `#8b949e` | something we do not own |

**Do not invent new colors.** A concept that fits none of these is Primary/neutral. Eight semantic
categories is already the ceiling — a ninth color stops encoding meaning and starts decorating.

## Text hierarchy

Free-floating text uses color for level, never size alone.

| Level | Hex | Use |
|---|---|---|
| Title | `#58a6ff` | one per diagram, the claim being argued |
| Subtitle | `#c4b5fd` | section labels, group headers |
| Body | `#c9d1d9` | text inside shapes, arrow labels |
| Detail | `#8b949e` | annotations, units, footnotes |
| Ghost | `#484f58` | watermarks, "before" state in a before/after |

Text **inside** a shape is always `body` (`#c9d1d9`), regardless of the shape's semantic color.
The shape already carries the meaning; recoloring its label doubles the encoding and halves the
contrast.

## Evidence artifacts

Code snippets, JSON payloads and terminal output are the one place a diagram quotes reality
verbatim. They get their own scheme so a reader can tell quoted evidence from authored claim.

| Part | Hex |
|---|---|
| Background | `#161b22` |
| Border | `#30363d` |
| Default code text | `#c9d1d9` |
| String literal | `#a5d6ff` |
| Keyword | `#ff7b72` |
| Function / identifier | `#d2a8ff` |
| Number / constant | `#79c0ff` |
| Comment | `#8b949e` |

Font for evidence: `fontFamily: 1` (monospace). Everything else: `fontFamily: 3` (hand-drawn).

## Arrows

| Purpose | Stroke | Style |
|---|---|---|
| Main flow | `#58a6ff` | solid, `strokeWidth: 2` |
| Secondary flow | `#8b949e` | solid, `strokeWidth: 1` |
| Failure / rejection | `#f85149` | dashed |
| Optional / conditional | `#8b949e` | dotted |
| Feedback loop | `#a855f7` | solid, curved |

## Light-mode override

The skill defaults to dark. If a diagram must be printed or embedded on a white page, swap only
the canvas and text tokens — the semantic strokes are chosen to hold on both surfaces:

| Token | Dark | Light |
|---|---|---|
| `canvas` | `#0d1117` | `#ffffff` |
| `surface` | `#161b22` | `#f6f8fa` |
| Body text | `#c9d1d9` | `#1f2328` |
| Title text | `#58a6ff` | `#0969da` |

Semantic fills invert to their tint (e.g. Decision `#3a2e0b` → `#fff8c5`); strokes stay as-is.
