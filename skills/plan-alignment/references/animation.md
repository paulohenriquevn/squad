# The animation, and why these three things together

A dot travelling along a line says *something moved*. It does not say what moved,
where it came from, or what happened when it arrived. The walkthrough animates
three things at once because those are the three questions a reader has.

| Layer | Technique | The question it answers |
|---|---|---|
| The edge draws itself | `stroke-dasharray` + `stroke-dashoffset`, length → 0 | Where did it come from, and in which direction |
| A packet rides it | CSS `offset-path` + `offset-distance` | What is moving |
| The destination pulses | a delayed `transform: scale` on a halo rect | It arrived — arrival is an EVENT |

## Why draw-on rather than a moving dot alone

`stroke-dashoffset` is the technique the whole field converged on, for reasons
that are not aesthetic:

- **It is GPU-composited.** Animating `stroke-dashoffset` does not trigger layout
  or repaint; animating `fill` or geometry does.
- **The drawing IS the duration.** Nothing has to be kept in sync by hand: the
  dash budget is the path's own `getTotalLength()`, written to `--len` per wire.
- **It reads as direction without an arrowhead.** A line that grows from A toward
  B has said which way it goes before the reader finds the marker.

```css
.wire.on.drawing {
  stroke-dasharray: var(--len); stroke-dashoffset: var(--len);
  animation: draw var(--dur) var(--ease) forwards;
}
@keyframes draw { to { stroke-dashoffset: 0; } }
```

`forwards` is required. Without `animation-fill-mode: forwards` the stroke snaps
back to invisible the instant the animation ends.

## Why `offset-path` and not SMIL `animateMotion`

`animateMotion` **translates from the element's current position**. A circle
placed at the wire's start therefore ends at start + path — twice the offset,
which parks the packet off-screen. The previous version hit this and fixed it by
zeroing `cx`/`cy`, a fix that works and that nobody can read.

CSS Motion Path has no such trap, composites on the same layer as the stroke, and
is styleable from the stylesheet rather than from attributes:

```css
.packet.run { offset-path: var(--track); animation: ride var(--dur) var(--ease) forwards; }
@keyframes ride { 0% { offset-distance: 0%; } 100% { offset-distance: 100%; } }
```

`--track` is set per packet to `path("<the same d as the wire>")`, so the packet
cannot drift from the line it is riding — they are literally the same geometry.

## Restarting a CSS animation

Removing and re-adding the class in one tick does nothing: the browser coalesces
both mutations and sees no change, so the step plays nothing. The layout has to
be flushed in between.

```js
w.path.classList.remove("drawing");
void w.path.getBoundingClientRect();   // forces a reflow; without this, no replay
w.path.classList.add("drawing");
```

The same applies to the arrival pulse, which is why `to` is removed, the layout
flushed, and `to` re-added — including on a step whose destination did not change.

## Duration

```js
const duration = len => Math.max(420, Math.min(1500, len * 2.1));
```

Distance-proportional with a floor and a ceiling. A short hop that takes as long
as a long one reads as a stall; a long one at the short one's speed is a blur.
The halo fires at 82% of the travel time, so the node begins reacting just before
the packet lands rather than after it.

## `prefers-reduced-motion` is not optional

```css
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
  .wire.on.drawing { stroke-dashoffset: 0; }
  .packet.run { offset-distance: 100%; opacity: 1; }
}
```

Disabling the animation is not enough — every animated property must be pinned to
its FINISHED state. Without the last two rules the wire stays invisible and the
packet sits at the origin, and someone who cannot use motion gets a blank stage
instead of a diagram. The walkthrough is a reading aid; for that reader it has to
degrade to a static diagram, not to nothing.

## The state hierarchy is part of the animation

Motion alone does not tell a reader where they are. Four node states and three
wire states carry that:

| State | Meaning |
|---|---|
| `.node.from` / `.node.to` | The two ends of THIS step |
| `.node.taking-part` (72%) | In this flow, not in this step |
| `.node.out` (20%, desaturated) | The flow never touches it |
| `.wire.on` | This step |
| `.wire.preview` (dashed, 38%) | Another step of this flow — where the packet came from and goes next |
| `.wire` | Not in this flow |

The distinction that matters is `taking-part` versus `out`. Collapsing them into
one grey — which the first version did — leaves the reader unable to see the path
and the current hop at the same time, and the animation becomes a light show.
