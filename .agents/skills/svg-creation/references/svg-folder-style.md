# SVG asset-folder conventions

Read this reference when creating or substantially editing diagrams in the selected `svg/` or `images/` folder.

## Location and neighboring files

- Treat the current working directory as the output boundary when it is already named `svg` or `images`; do not add another asset-directory layer beneath it.
- Otherwise, use the nearest relevant existing `svg/` or `images/` folder at or below the current working directory. Never create nested combinations such as `svg/svg/`, `svg/images/`, `images/svg/`, or `images/images/`.
- When an existing SVG or PNG etalon is the source or reference, use its containing asset folder for the new or revised SVG. Keeping same-stem SVG and PNG files together enables automatic reference comparison.
- Inspect nearby SVGs before introducing a new canvas size, font family, palette, component shape, or connector convention. Prefer a coherent folder over a one-off visual style.
- Preserve accessible metadata and useful XML comments found in well-maintained neighbors. Do not copy omissions from older or minimal examples.

## Visual language

- Use a high-contrast background and readable text unless the neighboring diagrams establish another accessible theme.
- Use a consistent font stack, title hierarchy, panel geometry, stroke weight, corner radius, and semantic palette within a folder.
- Favor panels, grids, and clearly separated sections over decorative effects in technical diagrams. Keep explanatory text legible at the image's likely display size.

## Teaching clarity and composition density

- Design for a viewer encountering the concept for the first time. The image should answer: what is being shown, where do I begin, what rule or relationship should I follow, and what result should I notice?
- Use an explicit visual sequence when the subject changes state: for example, before → rule → after, source → transformation → result, or step 1 → step 2 → step 3. Use visible labels rather than expecting color or position alone to explain the sequence.
- Define unfamiliar notation and make color semantics consistent. If the viewer must memorize a branch rule to read the image, place that rule next to the branch while keeping arrows clear of its text.
- Treat whitespace as a semantic resource, not default padding. Large gaps are acceptable only when they separate conceptual groups, protect readability, or provide a necessary routing corridor.
- After the first render, look for an empty center, oversized container, long connector corridor, or canvas margin that visually outweighs the information. Reflow or compress the layout and tighten the `viewBox`. Do not fill unused space with decoration or redundant text.
- Keep one dominant lesson and a small number of supporting details. A compact diagram is successful when it remains calm and readable, not when every coordinate is occupied.

## Arrow routing and layering

Treat an arrow as two visual parts with different overlap rules:

- **Shaft or path:** may cross or overlap non-text objects when this is necessary to show a relationship, dependency, sequence, or order. Use clear routing and sufficient contrast so the overlap reads as intentional.
- **Arrowhead:** must remain clear of every other object except its own shaft join. Its point may meet a destination boundary but must not enter the destination shape.
- **Text:** neither the shaft nor the arrowhead may cross, touch, underline, cover, or overlap text in any form. This includes headings, labels, captions, legends, annotations, and text placed inside shapes.

Separate a hand-drawn shaft and triangular head when exact geometry matters. Stop the shaft at or slightly inside its own head's base to hide the join. For markers, make the viewport, `refX`, `refY`, orientation, and units explicit, then inspect the rendered head at the final size.

There is no universal connector layer. A shaft may sit above or below a shape according to the relationship being shown. Keep text visually above crossing geometry and keep arrowheads fully visible. Add a concise XML comment when an unusual crossing or layer choice would otherwise look accidental.

### Marker nose joins

SVG paints a marker-ended shaft all the way to the path endpoint. If a triangular marker registers `refX` at its sharp tip, the stroked shaft can remain visible through the last narrow part of the triangle and look like a rectangular tail after the apparent nose.

- Register the marker slightly behind its tip so the tip projects forward and the shaft endpoint lies under a part of the head wide enough to cover the entire stroke. Include antialiasing clearance rather than matching the mathematical edges exactly.
- With `markerUnits="userSpaceOnUse"`, a 2-unit shaft, and this common 18×16 triangle, a 2-unit projection is a useful starting point:

  ```xml
  <!-- The tip at x=18 projects 2 units beyond the shaft endpoint at refX=16. -->
  <marker id="arrowhead" markerWidth="18" markerHeight="16"
          viewBox="0 0 18 16" refX="16" refY="8"
          orient="auto" markerUnits="userSpaceOnUse">
    <path d="M0 0 L18 8 L0 16 Z" fill="#000"/>
  </marker>
  ```

- Scale the projection for the actual shaft width, head taper, and `markerUnits`. The head's cross-section at the path endpoint must cover the shaft; 1–2 units is not a universal value.
- Compensate for the forward projection when placing the connector. If the desired visible tip is target point `T`, projection distance is `d`, and `u` is the final unit direction, place the path endpoint at `T − d·u`. For a cubic Bézier, use its final tangent direction. This keeps the nose on the target boundary instead of pushing it inside the target.
- Use one join convention for all equivalent arrows. After changing a shared marker, inspect every reference to it and every orientation. Separate variants are appropriate only when stroke width, head geometry, or target geometry differs; document the exception beside the definition.

At 8×–10× zoom, reject all three failure modes: a shaft tail visible beyond the tapered nose, a white gap between nose and target, or a nose that penetrates the target boundary.

## Text layout

SVG does not wrap text automatically. Split long labels into deliberate lines, provide consistent line height, and leave generous padding from borders and all arrow geometry. Render with realistic fallback fonts before finalizing container dimensions.

For dense diagrams, preserve a hierarchy of title, section heading, node label, annotation, and footer sizes. Review both the complete composition and zoomed regions because a diagram can fit the `viewBox` while remaining unreadable at its actual display size.

## Repair-oriented comments

Prefer comments that help a maintainer find or safely change a region:

```xml
<!-- Relation path intentionally crosses the process box; keep it clear of the label. -->
<!-- Arrowhead stops at the target border and must not enter the node. -->
<!-- Legend; keep within the bottom safe area when adding categories. -->
```

Avoid comments that merely repeat an element name, such as `<!-- rectangle -->`.
