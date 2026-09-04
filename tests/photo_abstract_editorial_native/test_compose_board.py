"""End-to-end tests for the board composer, run the way the skill runs it.

Every case goes through the CLI rather than the module: the skill's step 2 is a
command, so the command is the boundary worth holding. The geometry assertions
recompute the contract's arithmetic from the source dimensions instead of
restating a pixel count, so a deliberate change to a share moves one constant and
not a table of magic numbers.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "photography" / "skills" / "photo-abstract-editorial-native"
COMPOSE = SKILL / "scripts" / "compose_board.py"

IVORY = (243, 240, 232)


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(COMPOSE), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


class HelpTests(unittest.TestCase):
    """--help must answer without Pillow: the evaluation runner renders it."""

    def test_help_needs_no_imaging_dependency(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", "-c", HELP_WITHOUT_PILLOW],
            capture_output=True,
            text=True,
            check=False,
            cwd=SKILL,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--source-class", result.stdout)
        self.assertIn("--lower-art", result.stdout)


HELP_WITHOUT_PILLOW = """
import runpy, sys


class Blocked:
    def find_spec(self, name, path=None, target=None):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("PIL is blocked for this test")
        return None


sys.meta_path.insert(0, Blocked())
sys.argv = ["compose_board.py", "--help"]
try:
    runpy.run_path("scripts/compose_board.py", run_name="__main__")
except SystemExit as exit:
    sys.exit(exit.code or 0)
"""


@unittest.skipUnless(pillow_available(), "Pillow is not installed")
class ComposeBoardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.workspace = Path(self._directory.name)

    def write_image(self, name: str, size: tuple[int, int], colour: str = "#3366AA") -> Path:
        from PIL import Image

        path = self.workspace / name
        Image.new("RGB", size, colour).save(path)
        return path

    def compose(
        self,
        source: tuple[int, int],
        lower: tuple[int, int],
        *extra: str,
        source_class: str = "original",
    ) -> dict:
        source_path = self.write_image("source.png", source)
        lower_path = self.write_image("lower.png", lower, "#AA6633")
        out = self.workspace / "board.png"
        result = run(
            "--source",
            str(source_path),
            "--lower-art",
            str(lower_path),
            "--out",
            str(out),
            "--source-class",
            source_class,
            *extra,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(out.is_file())
        manifest = json.loads((self.workspace / "board.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["board"]["dimensions"], list(self.board_size(out)))
        return manifest

    @staticmethod
    def board_size(path: Path) -> tuple[int, int]:
        from PIL import Image

        with Image.open(path) as board:
            return board.width, board.height

    def test_landscape_takes_the_wide_row_of_the_ratio_table(self) -> None:
        manifest = self.compose((2000, 1200), (900, 600))

        expected_lower = round(max(0.55 * 2000, 0.85 * 1200))
        self.assertEqual(manifest["board"]["layout"], "top-and-bottom")
        self.assertEqual(manifest["board"]["dimensions"], [2000, 1200 + expected_lower])
        self.assertEqual(manifest["top"]["dimensions"], [2000, 1200])

    def test_square_source_takes_the_middle_row(self) -> None:
        manifest = self.compose((1500, 1500), (600, 400))

        expected_lower = round(max(0.68 * 1500, 0.70 * 1500))
        self.assertEqual(manifest["board"]["dimensions"], [1500, 1500 + expected_lower])

    def test_the_tall_row_decides_the_exception_rather_than_a_delivered_board(self) -> None:
        """A portrait source always takes the exception, and that follows from the table.

        The tall row reserves `max(0.85 x width, 0.58 x top height)` below the
        photograph, and no ratio at or under 0.85 produces a stacked board within
        the 1.8x trigger — the algebra has no solution. So the row's real job is to
        size the hypothetical board the trigger measures, and a portrait source is
        never delivered top-and-bottom. A change that made one reachable would be a
        change to the contract, and this is the case that would notice.
        """

        manifest = self.compose((1200, 1500), (600, 400))
        self.assertEqual(manifest["board"]["layout"], "portrait-side-by-side")

        standard_lower = round(max(0.85 * 1200, 0.58 * 1500))
        self.assertGreater(1500 + standard_lower, 1.8 * 1200)

    def test_very_tall_portrait_takes_the_side_by_side_exception(self) -> None:
        manifest = self.compose((800, 2400), (600, 400))

        field_width = round(0.60 * 2400)
        self.assertEqual(manifest["board"]["layout"], "portrait-side-by-side")
        self.assertEqual(manifest["board"]["dimensions"], [800 + field_width, 2400])
        self.assertEqual(manifest["top"]["dimensions"], [800, 2400])

    def test_the_source_sits_at_the_left_edge_of_a_side_by_side_board(self) -> None:
        from PIL import Image

        source_path = self.write_image("source.png", (800, 2400), "#3366AA")
        lower_path = self.write_image("lower.png", (600, 400), "#AA6633")
        out = self.workspace / "board.png"
        result = run(
            "--source",
            str(source_path),
            "--lower-art",
            str(lower_path),
            "--out",
            str(out),
            "--source-class",
            "original",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        with Image.open(out) as board:
            self.assertEqual(board.getpixel((5, 5)), (51, 102, 170))
            self.assertEqual(board.getpixel((board.width - 5, 5)), IVORY)

    def test_a_small_lower_panel_is_never_enlarged(self) -> None:
        manifest = self.compose((2000, 1200), (120, 90))

        self.assertEqual(manifest["lower_art"]["dimensions_after_fit"], [120, 90])
        self.assertFalse(manifest["lower_upscaled"])
        self.assertEqual(manifest["resize_operations"], [])

    def test_an_oversized_lower_panel_shrinks_inside_its_breathing_room(self) -> None:
        manifest = self.compose((2000, 1200), (4000, 1000))

        board_width, board_height = manifest["board"]["dimensions"]
        lower_height = board_height - manifest["top"]["dimensions"][1]
        width, height = manifest["lower_art"]["dimensions_after_fit"]
        self.assertLessEqual(width, round(0.90 * board_width))
        self.assertLessEqual(height, round(0.78 * lower_height))
        self.assertLess(abs(width / height - 4000 / 1000) / (4000 / 1000), 0.001)
        self.assertFalse(manifest["lower_upscaled"])
        self.assertIn("shrink lower-art", manifest["resize_operations"][0])

    def test_a_source_over_the_delivery_limit_is_downscaled_not_stretched(self) -> None:
        manifest = self.compose((3000, 2000), (600, 400), "--max-edge", "1500")

        width, height = manifest["top"]["dimensions"]
        self.assertEqual(width, 1500)
        self.assertLess(abs(width / height - 3000 / 2000) / (3000 / 2000), 0.001)
        self.assertFalse(manifest["top_upscaled"])
        self.assertTrue(manifest["aspect_ratio_preserved"])
        self.assertIn("downscale source", manifest["resize_operations"][0])

    def test_a_source_under_the_delivery_limit_is_left_alone(self) -> None:
        manifest = self.compose((900, 600), (300, 200), "--max-edge", "4096")

        self.assertEqual(manifest["top"]["dimensions"], [900, 600])
        self.assertFalse(manifest["top_upscaled"])

    def test_the_manifest_records_provenance_and_both_panels(self) -> None:
        manifest = self.compose((2000, 1200), (900, 600))

        self.assertEqual(manifest["source"]["class"], "original")
        self.assertEqual(manifest["source"]["dimensions_before_orientation"], [2000, 1200])
        self.assertEqual(manifest["source"]["dimensions_after_orientation"], [2000, 1200])
        self.assertEqual(manifest["lower_art"]["dimensions_before_fit"], [900, 600])
        self.assertTrue(manifest["aspect_ratio_preserved"])
        self.assertNotIn("audit_note", manifest)

    def test_a_derivative_fallback_carries_a_visible_audit_note(self) -> None:
        manifest = self.compose((2000, 1200), (900, 600), source_class="derivative-fallback")

        self.assertEqual(manifest["source"]["class"], "derivative-fallback")
        self.assertIn("not the original", manifest["audit_note"])

    def test_an_exif_rotated_source_is_oriented_before_the_geometry_is_chosen(self) -> None:
        from PIL import Image

        # Orientation 6: stored landscape, displayed portrait.
        exif = Image.Exif()
        exif[274] = 6
        source_path = self.workspace / "rotated.jpg"
        Image.new("RGB", (2400, 800), "#3366AA").save(source_path, exif=exif)
        lower_path = self.write_image("lower.png", (600, 400), "#AA6633")
        out = self.workspace / "board.jpg"

        result = run(
            "--source",
            str(source_path),
            "--lower-art",
            str(lower_path),
            "--out",
            str(out),
            "--source-class",
            "original",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        manifest = json.loads((self.workspace / "board.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"]["dimensions_before_orientation"], [2400, 800])
        self.assertEqual(manifest["source"]["dimensions_after_orientation"], [800, 2400])
        self.assertEqual(manifest["board"]["layout"], "portrait-side-by-side")
        self.assertIn("auto-orient", manifest["resize_operations"][0])

    def test_the_canvas_colour_is_the_contract_ivory_by_default(self) -> None:
        from PIL import Image

        source_path = self.write_image("source.png", (2000, 1200))
        lower_path = self.write_image("lower.png", (120, 90), "#AA6633")
        out = self.workspace / "board.png"
        result = run(
            "--source",
            str(source_path),
            "--lower-art",
            str(lower_path),
            "--out",
            str(out),
            "--source-class",
            "original",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        with Image.open(out) as board:
            self.assertEqual(board.getpixel((5, board.height - 5)), IVORY)

    def test_a_named_manifest_path_is_honoured(self) -> None:
        source_path = self.write_image("source.png", (2000, 1200))
        lower_path = self.write_image("lower.png", (900, 600), "#AA6633")
        sidecar = self.workspace / "audit" / "record.json"
        result = run(
            "--source",
            str(source_path),
            "--lower-art",
            str(lower_path),
            "--out",
            str(self.workspace / "board.png"),
            "--source-class",
            "cloud-original",
            "--manifest",
            str(sidecar),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8"))["source"]["class"], "cloud-original")


@unittest.skipUnless(pillow_available(), "Pillow is not installed")
class ComposeBoardFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.workspace = Path(self._directory.name)

    def test_an_unreadable_source_is_reported_not_swallowed(self) -> None:
        from PIL import Image

        lower_path = self.workspace / "lower.png"
        Image.new("RGB", (600, 400), "#AA6633").save(lower_path)
        broken = self.workspace / "broken.jpg"
        broken.write_text("not an image", encoding="utf-8")

        result = run(
            "--source",
            str(broken),
            "--lower-art",
            str(lower_path),
            "--out",
            str(self.workspace / "board.png"),
            "--source-class",
            "original",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot read source", result.stderr)

    def test_an_unknown_source_class_is_refused(self) -> None:
        from PIL import Image

        path = self.workspace / "image.png"
        Image.new("RGB", (600, 400), "#AA6633").save(path)

        result = run(
            "--source",
            str(path),
            "--lower-art",
            str(path),
            "--out",
            str(self.workspace / "board.png"),
            "--source-class",
            "screenshot",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--source-class", result.stderr)

    def test_a_nonpositive_delivery_limit_is_refused(self) -> None:
        from PIL import Image

        path = self.workspace / "image.png"
        Image.new("RGB", (600, 400), "#AA6633").save(path)

        result = run(
            "--source",
            str(path),
            "--lower-art",
            str(path),
            "--out",
            str(self.workspace / "board.png"),
            "--source-class",
            "original",
            "--max-edge",
            "0",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--max-edge must be positive", result.stderr)

    def test_no_board_is_left_on_disk_when_the_run_is_refused(self) -> None:
        from PIL import Image

        path = self.workspace / "image.png"
        Image.new("RGB", (600, 400), "#AA6633").save(path)
        out = self.workspace / "board.png"

        run(
            "--source",
            str(path),
            "--lower-art",
            str(path),
            "--out",
            str(out),
            "--source-class",
            "original",
            "--max-edge",
            "-1",
        )

        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
