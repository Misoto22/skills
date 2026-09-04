#!/usr/bin/env python3
"""Compose the comparison board the composition contract describes, and prove it.

The contract in `references/composition-contract.md` is arithmetic: a ratio table
picking the lower-canvas height, a shrink-only fit, an aspect-ratio tolerance of
0.1%, and three manifest booleans. Prose asks a model to re-derive that on every
run, and the two failures the skill exists to prevent — a soft upper photo and a
squashed lower panel — are exactly what a re-derivation gets wrong. So the
geometry is computed here and the contract text stays as the explanation.

The booleans are computed, never asserted. An upscale or a ratio drift past the
tolerance ends the run with a message naming the measurement, rather than writing
`aspect_ratio_preserved: true` over a board that was stretched.

  python3 scripts/compose_board.py --source photo.jpg --lower-art panel.png \\
      --out board.jpg --source-class original

Pillow is the one dependency, declared in this skill's own `requirements.txt`.
Decoding, EXIF orientation and resampling are not work a dependency-free script
can do, and re-implementing them would be a second imaging library nobody here
could test. It is imported lazily so `--help` answers on a machine that has not
installed it yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# The contract's ivory. Overridable because it names "a comparably neutral,
# uniform ivory" as equally acceptable, and a house palette may differ.
IVORY = "#F3F0E8"

# The contract's ratio table. Each row is (lower bound on width/height, share of
# board width, share of top height); the lower canvas takes the larger of the two
# shares. Ordered widest first, so the first matching row wins.
RATIO_TABLE = (
    (1.25, 0.55, 0.85),
    (0.85, 0.68, 0.70),
    (0.0, 0.85, 0.58),
)

# Breathing room for the lower panel, inside the lower canvas and inside the
# side-by-side field alike.
LOWER_WIDTH_SHARE = 0.90
LOWER_HEIGHT_SHARE = 0.78

# The side-by-side field, as a share of the source height.
SIDE_FIELD_SHARE = 0.60

# A standard board taller than this multiple of its width triggers the exception.
SIDE_BY_SIDE_TRIGGER = 1.8

# The contract's tolerance: a larger error means a stretch or the wrong source.
ASPECT_TOLERANCE = 0.001

SOURCE_CLASSES = ("original", "photos-export", "cloud-original", "derivative-fallback")

DERIVATIVE_NOTE = (
    "Top panel is a derivative rendition, not the original file."
    " Do not describe this board as composed from the original."
)


def _load_pillow() -> tuple[Any, Any]:
    """Import Pillow, or explain how to install it.

    Lazy so that `--help` works uninstalled: the evaluation runner renders the
    help text of every script SKILL.md names, in an environment that has no
    reason to carry this skill's dependency.
    """

    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise SystemExit(
            "error: Pillow is required to compose a board.\n"
            "  uv pip install -r requirements.txt    (from this skill's directory)\n"
            "  pip install -r requirements.txt       (where uv is unavailable)"
        ) from error
    return Image, ImageOps


def _ratio_error(before: tuple[int, int], after: tuple[int, int]) -> float:
    """Return the relative aspect-ratio change between two sizes."""

    original = before[0] / before[1]
    return abs(after[0] / after[1] - original) / original


def _fit_within(size: tuple[int, int], box: tuple[int, int]) -> tuple[int, int]:
    """Return `size` shrunk to fit `box`, never enlarged.

    ImageMagick's `>` geometry, in three lines: a scale above 1 is discarded, so
    a panel smaller than its box keeps the dimensions the artist gave it.
    """

    scale = min(box[0] / size[0], box[1] / size[1], 1.0)
    return max(1, round(size[0] * scale)), max(1, round(size[1] * scale))


def _lower_canvas_height(size: tuple[int, int], board_width: int) -> int:
    """Return the lower-canvas height the contract's ratio table gives this source."""

    ratio = size[0] / size[1]
    for lower_bound, width_share, top_share in RATIO_TABLE:
        if ratio >= lower_bound:
            return round(max(width_share * board_width, top_share * size[1]))
    raise AssertionError("the ratio table's last row has a lower bound of zero")


def _resized(image: Any, size: tuple[int, int], resample: Any) -> Any:
    """Return `image` at `size`, or `image` itself when the size is unchanged."""

    if (image.width, image.height) == size:
        return image
    return image.resize(size, resample)


def _prepare_source(path: Path, max_edge: int) -> dict[str, Any]:
    """Decode, auto-orient and downscale the source, recording every step."""

    Image, ImageOps = _load_pillow()
    try:
        decoded = Image.open(path)
        decoded.load()
    except (OSError, ValueError) as error:
        raise SystemExit(f"error: cannot read source {path}: {error}") from error

    before = (decoded.width, decoded.height)
    oriented = ImageOps.exif_transpose(decoded) or decoded
    after = (oriented.width, oriented.height)

    operations: list[str] = []
    if before != after:
        operations.append(f"auto-orient {before[0]}x{before[1]} -> {after[0]}x{after[1]}")

    target = _fit_within(after, (max_edge, max_edge))
    if target != after:
        operations.append(f"downscale source {after[0]}x{after[1]} -> {target[0]}x{target[1]}")
    top = _resized(oriented.convert("RGB"), target, Image.LANCZOS)

    error = _ratio_error(after, target)
    if error > ASPECT_TOLERANCE:
        raise SystemExit(
            f"error: source aspect ratio moved by {error:.4%} (tolerance {ASPECT_TOLERANCE:.1%});"
            " the image would be stretched"
        )
    return {
        "image": top,
        "before_orientation": before,
        "after_orientation": after,
        "operations": operations,
        "aspect_error": error,
    }


def _prepare_lower(path: Path, box: tuple[int, int]) -> dict[str, Any]:
    """Decode the lower panel and shrink it into `box` without enlarging it."""

    Image, _ = _load_pillow()
    try:
        panel = Image.open(path)
        panel.load()
    except (OSError, ValueError) as error:
        raise SystemExit(f"error: cannot read lower art {path}: {error}") from error

    before = (panel.width, panel.height)
    after = _fit_within(before, box)
    error = _ratio_error(before, after)
    if error > ASPECT_TOLERANCE:
        raise SystemExit(
            f"error: lower-art aspect ratio moved by {error:.4%} (tolerance {ASPECT_TOLERANCE:.1%});"
            " the panel would be squashed"
        )
    operations = []
    if after != before:
        operations.append(f"shrink lower-art {before[0]}x{before[1]} -> {after[0]}x{after[1]}")
    return {
        "image": _resized(panel.convert("RGB"), after, Image.LANCZOS),
        "before_fit": before,
        "after_fit": after,
        "operations": operations,
        "aspect_error": error,
    }


def _stacked_geometry(top: tuple[int, int]) -> dict[str, Any]:
    """Return the standard top-and-bottom board's dimensions and lower-art box."""

    board_width = top[0]
    lower_height = _lower_canvas_height(top, board_width)
    return {
        "layout": "top-and-bottom",
        "board": (board_width, top[1] + lower_height),
        "field": (0, top[1], board_width, lower_height),
        "box": (
            max(1, round(LOWER_WIDTH_SHARE * board_width)),
            max(1, round(LOWER_HEIGHT_SHARE * lower_height)),
        ),
    }


def _side_by_side_geometry(top: tuple[int, int]) -> dict[str, Any]:
    """Return the portrait exception's dimensions and lower-art box.

    The field's own breathing room is the same 90% and 78% the standard layout
    uses; the contract fixes only the field's width.
    """

    field_width = max(1, round(SIDE_FIELD_SHARE * top[1]))
    return {
        "layout": "portrait-side-by-side",
        "board": (top[0] + field_width, top[1]),
        "field": (top[0], 0, field_width, top[1]),
        "box": (
            max(1, round(LOWER_WIDTH_SHARE * field_width)),
            max(1, round(LOWER_HEIGHT_SHARE * top[1])),
        ),
    }


def _geometry(top: tuple[int, int]) -> dict[str, Any]:
    """Pick the layout, applying the portrait exception only when both tests pass."""

    stacked = _stacked_geometry(top)
    portrait = top[0] / top[1] <= 0.85
    too_tall = stacked["board"][1] > SIDE_BY_SIDE_TRIGGER * stacked["board"][0]
    return _side_by_side_geometry(top) if portrait and too_tall else stacked


def _render(source: dict[str, Any], lower: dict[str, Any], geometry: dict[str, Any], canvas: str) -> Any:
    """Paint the board: source at its edge, lower panel centred in the ivory field."""

    Image, _ = _load_pillow()
    board = Image.new("RGB", geometry["board"], canvas)
    board.paste(source["image"], (0, 0))

    field_x, field_y, field_width, field_height = geometry["field"]
    panel_width, panel_height = lower["after_fit"]
    board.paste(
        lower["image"],
        (
            field_x + (field_width - panel_width) // 2,
            field_y + (field_height - panel_height) // 2,
        ),
    )
    return board


def _manifest(
    arguments: argparse.Namespace,
    source: dict[str, Any],
    lower: dict[str, Any],
    geometry: dict[str, Any],
) -> dict[str, Any]:
    """Return the sidecar the contract requires, with its booleans measured."""

    delivered = (source["image"].width, source["image"].height)
    top_upscaled = any(
        after > before for before, after in zip(source["after_orientation"], delivered, strict=True)
    )
    lower_upscaled = any(
        after > before for before, after in zip(lower["before_fit"], lower["after_fit"], strict=True)
    )
    manifest: dict[str, Any] = {
        "source": {
            "path": str(arguments.source),
            "class": arguments.source_class,
            "dimensions_before_orientation": list(source["before_orientation"]),
            "dimensions_after_orientation": list(source["after_orientation"]),
        },
        "board": {
            "layout": geometry["layout"],
            "dimensions": list(geometry["board"]),
            "canvas": arguments.canvas,
            "output": str(arguments.out),
        },
        "top": {"dimensions": [source["image"].width, source["image"].height]},
        "lower_art": {
            "path": str(arguments.lower_art),
            "dimensions_before_fit": list(lower["before_fit"]),
            "dimensions_after_fit": list(lower["after_fit"]),
        },
        "resize_operations": source["operations"] + lower["operations"],
        "aspect_ratio_error": {
            "top": round(source["aspect_error"], 6),
            "lower": round(lower["aspect_error"], 6),
            "tolerance": ASPECT_TOLERANCE,
        },
        "top_upscaled": top_upscaled,
        "lower_upscaled": lower_upscaled,
        "aspect_ratio_preserved": max(source["aspect_error"], lower["aspect_error"]) <= ASPECT_TOLERANCE,
    }
    if arguments.source_class == "derivative-fallback":
        manifest["audit_note"] = DERIVATIVE_NOTE
    return manifest


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose a proportion-safe photo comparison board.")
    parser.add_argument("--source", type=Path, required=True, help="the original photograph")
    parser.add_argument("--lower-art", type=Path, required=True, help="the supplied abstract panel")
    parser.add_argument("--out", type=Path, required=True, help="where to write the composed board")
    parser.add_argument(
        "--source-class",
        required=True,
        choices=SOURCE_CLASSES,
        help="how the source was obtained; derivative-fallback adds a visible audit note",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="where to write the sidecar JSON (default: the output path with .manifest.json)",
    )
    parser.add_argument(
        "--max-edge",
        type=int,
        default=4096,
        help="delivery limit in pixels; the source is downscaled to it and never upscaled",
    )
    parser.add_argument("--canvas", default=IVORY, help=f"the artwork field colour (default: {IVORY})")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    if arguments.max_edge < 1:
        raise SystemExit(f"error: --max-edge must be positive; got {arguments.max_edge}")

    source = _prepare_source(arguments.source, arguments.max_edge)
    top = (source["image"].width, source["image"].height)
    geometry = _geometry(top)
    lower = _prepare_lower(arguments.lower_art, geometry["box"])

    # Refuse before writing anything: a rejected board left on disk is the one
    # that gets delivered, and the manifest is the record that it was checked.
    manifest = _manifest(arguments, source, lower, geometry)
    if manifest["top_upscaled"] or manifest["lower_upscaled"]:
        raise SystemExit("error: a panel was enlarged; the board is not source-faithful")
    if not manifest["aspect_ratio_preserved"]:
        raise SystemExit("error: a panel was stretched; the board is not source-faithful")

    board = _render(source, lower, geometry, arguments.canvas)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        board.save(arguments.out, quality=92)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"error: cannot write {arguments.out}: {error}") from error

    path = arguments.manifest or arguments.out.with_suffix(".manifest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {arguments.out} ({geometry['board'][0]}x{geometry['board'][1]}, {geometry['layout']})")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
