# Composition Contract

Use this contract after both `source` and `lower-art` are available.

## Source treatment

1. Decode and auto-orient the source first.
2. Preserve its whole frame and aspect ratio. Do not crop, extend, retouch, recolour, blur, sharpen, or apply a filter.
3. Set the board width from the source. Downscale the source only when either dimension would exceed the chosen delivery limit. Never upscale it.
4. Place that resulting image, unmodified, at the top edge of the board unless the portrait side-by-side exception below applies.

The source aspect-ratio error after any resize must be at most 0.1%. A larger error means the image was stretched or an incorrect source was selected.

## Standard top-and-bottom geometry

Use an ivory canvas (`#F3F0E8` or a comparably neutral, uniform ivory) below the photograph. Pick a lower canvas height from the oriented source ratio:

| Source ratio | Minimum lower-canvas height |
| --- | --- |
| Landscape, width ÷ height at least 1.25 | `max(0.55 × board width, 0.85 × top height)` |
| Portrait, width ÷ height at most 0.85 | `max(0.85 × board width, 0.58 × top height)` |
| Between those ratios | `max(0.68 × board width, 0.70 × top height)` |

Fit `lower-art` inside 90% of the board width and 78% of the lower-canvas height with aspect ratio preserved. Use a resize operation equivalent to ImageMagick's `>` geometry: it may shrink a panel but never enlarge it. Centre the panel in the lower canvas.

Do not force the lower panel to the source ratio. Its white space and title are part of the artwork.

## Portrait side-by-side exception

Use this exception only when both conditions are true:

1. The oriented source width divided by height is at most `0.85`.
2. The standard top-and-bottom board would be taller than `1.8 ×` its width.

Set the board height to the source height. Place the complete, unmodified source on the left edge. Use an ivory artwork field on the right whose width is at least `0.60 × source height`; centre `lower-art` in that field without enlarging it, giving it the same breathing room the standard layout does — 90% of the field width and 78% of the board height. This keeps the source on the left and lower-art on the right while avoiding an excessively tall document.

Every portrait source reaches this exception. The tall row of the table above reserves enough lower canvas that no ratio at or below `0.85` produces a standard board within the `1.8 ×` trigger, so that row's work is to size the board the trigger measures rather than one that is ever delivered.

Keep the source and artwork field visually separate, but do not add a decorative border, a forced divider, a crop, or a ratio-matching resize. Preserve the lower panel's title and required white space.

## Manifest and acceptance checks

Write a sidecar JSON or TSV with:

- source file and source class: `original`, `photos-export`, `cloud-original`, or `derivative-fallback`;
- source dimensions before and after auto-orientation;
- board dimensions and top-image dimensions;
- lower-art dimensions before and after fitting;
- `top_upscaled: false`, `lower_upscaled: false`, and `aspect_ratio_preserved: true`.

Accept the board only when the top section is pixel-faithful and visually crisp, the lower art is not stretched, and all three boolean assertions are true. A derivative fallback is allowed only with a visible audit note; it must not be described as an original.
