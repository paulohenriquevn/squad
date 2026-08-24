# Element Templates

Copy-paste JSON for each Excalidraw element type. Colors are placeholders written as
`{{fill}}` / `{{stroke}}` / `{{text}}` — substitute the real hex from
[`color-palette.md`](color-palette.md) based on the element's **semantic purpose**, never by taste.

Every element needs a unique `id`. `seed` and `versionNonce` can be any integer; Excalidraw
rewrites them on first edit. `groupIds: []` unless the element belongs to a group.

## Rectangle (a labelled box)

A box is two elements: the container and its bound text. They reference each other —
`boundElements` on the rectangle, `containerId` on the text. Omitting either renders a box with
an unanchored label floating beside it.

```json
{
  "type": "rectangle",
  "id": "box1",
  "x": 200, "y": 150, "width": 180, "height": 90,
  "angle": 0,
  "strokeColor": "{{stroke}}",
  "backgroundColor": "{{fill}}",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "roundness": { "type": 3 },
  "seed": 1,
  "version": 1,
  "versionNonce": 1,
  "isDeleted": false,
  "groupIds": [],
  "frameId": null,
  "boundElements": [{ "id": "box1text", "type": "text" }],
  "updated": 1,
  "link": null,
  "locked": false
}
```

```json
{
  "type": "text",
  "id": "box1text",
  "x": 210, "y": 185, "width": 160, "height": 20,
  "angle": 0,
  "strokeColor": "#c9d1d9",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "seed": 2,
  "version": 1,
  "versionNonce": 2,
  "isDeleted": false,
  "groupIds": [],
  "frameId": null,
  "boundElements": null,
  "updated": 1,
  "link": null,
  "locked": false,
  "fontSize": 16,
  "fontFamily": 3,
  "text": "Readable words only",
  "originalText": "Readable words only",
  "textAlign": "center",
  "verticalAlign": "middle",
  "containerId": "box1",
  "lineHeight": 1.25
}
```

## Free-floating text (no container)

The default. `SKILL.md` targets under 30% of text inside containers — a label does not need a box
to be read. Use the **text hierarchy** colors, not the semantic shape colors.

```json
{
  "type": "text",
  "id": "title1",
  "x": 200, "y": 60, "width": 400, "height": 32,
  "angle": 0,
  "strokeColor": "#58a6ff",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "seed": 3,
  "version": 1,
  "versionNonce": 3,
  "isDeleted": false,
  "groupIds": [],
  "frameId": null,
  "boundElements": null,
  "updated": 1,
  "link": null,
  "locked": false,
  "fontSize": 24,
  "fontFamily": 3,
  "text": "The claim this diagram argues",
  "originalText": "The claim this diagram argues",
  "textAlign": "left",
  "verticalAlign": "top",
  "containerId": null,
  "lineHeight": 1.25
}
```

## Arrow (a relationship)

`startBinding` / `endBinding` glue the arrow to shapes so it follows them when they move. `points`
are **relative to `x`/`y`**, and the first point is always `[0, 0]`.

```json
{
  "type": "arrow",
  "id": "arrow1",
  "x": 380, "y": 195, "width": 120, "height": 0,
  "angle": 0,
  "strokeColor": "#58a6ff",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "seed": 4,
  "version": 1,
  "versionNonce": 4,
  "isDeleted": false,
  "groupIds": [],
  "frameId": null,
  "roundness": { "type": 2 },
  "boundElements": null,
  "updated": 1,
  "link": null,
  "locked": false,
  "points": [[0, 0], [120, 0]],
  "lastCommittedPoint": null,
  "startBinding": { "elementId": "box1", "focus": 0, "gap": 4 },
  "endBinding": { "elementId": "box2", "focus": 0, "gap": 4 },
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

For a **dashed failure arrow**: `"strokeStyle": "dashed"`, `"strokeColor": "#f85149"`.
For a **feedback loop**: add a mid-point, e.g. `"points": [[0,0],[60,80],[120,0]]`.

## Line (a divider or an axis)

Same shape as an arrow without arrowheads. Use for timelines, axes and section rules — a line
carries no direction, so it never substitutes for an arrow between two related things.

```json
{
  "type": "line",
  "id": "line1",
  "x": 100, "y": 400, "width": 600, "height": 0,
  "angle": 0,
  "strokeColor": "#30363d",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "seed": 5,
  "version": 1,
  "versionNonce": 5,
  "isDeleted": false,
  "groupIds": [],
  "frameId": null,
  "roundness": null,
  "boundElements": null,
  "updated": 1,
  "link": null,
  "locked": false,
  "points": [[0, 0], [600, 0]],
  "lastCommittedPoint": null,
  "startBinding": null,
  "endBinding": null,
  "startArrowhead": null,
  "endArrowhead": null
}
```

## Dot (a point on a timeline)

An ellipse small enough to read as a marker. Keep `roughness: 0` — a hand-drawn wobble on a 12px
circle reads as a smudge.

```json
{
  "type": "ellipse",
  "id": "dot1",
  "x": 200, "y": 394, "width": 12, "height": 12,
  "angle": 0,
  "strokeColor": "#58a6ff",
  "backgroundColor": "#58a6ff",
  "fillStyle": "solid",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "seed": 6,
  "version": 1,
  "versionNonce": 6,
  "isDeleted": false,
  "groupIds": [],
  "frameId": null,
  "roundness": { "type": 2 },
  "boundElements": null,
  "updated": 1,
  "link": null,
  "locked": false
}
```

## Evidence artifact (quoted code or JSON)

A `surface` panel with monospace text — `fontFamily: 1`, not 3. This is the one element that
quotes reality verbatim, so it must look different from authored claims.

```json
{
  "type": "rectangle",
  "id": "evidence1",
  "x": 150, "y": 480, "width": 460, "height": 120,
  "angle": 0,
  "strokeColor": "#30363d",
  "backgroundColor": "#161b22",
  "fillStyle": "solid",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 0,
  "opacity": 100,
  "roundness": { "type": 3 },
  "seed": 7,
  "version": 1,
  "versionNonce": 7,
  "isDeleted": false,
  "groupIds": [],
  "frameId": null,
  "boundElements": [{ "id": "evidence1text", "type": "text" }],
  "updated": 1,
  "link": null,
  "locked": false
}
```

The bound text uses `"fontFamily": 1`, `"fontSize": 13`, `"textAlign": "left"`,
`"verticalAlign": "top"`, `"strokeColor": "#c9d1d9"`.

## Scene skeleton

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [],
  "appState": {
    "viewBackgroundColor": "#0d1117",
    "gridSize": 20
  },
  "files": {}
}
```
