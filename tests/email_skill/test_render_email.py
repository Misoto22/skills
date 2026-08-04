from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "skills" / "email" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from render_email import normalize_text, render_html  # noqa: E402


def style_profile(**overrides: object) -> dict[str, object]:
    """Return a complete, already-validated style profile for rendering tests."""

    profile: dict[str, object] = {
        "font_family": "Helvetica, Arial, sans-serif",
        "font_size_px": 14,
        "line_height": 1.55,
        "text_color": "#222222",
        "paragraph_spacing_px": 16,
        "list_style": "semantic",
        "table": {
            "border_color": "#cccccc",
            "font_size_px": 13,
            "cell_padding_px": [6, 10],
        },
        "status_colors": {
            "ok": "#1a7f37",
            "warn": "#b36b00",
            "bad": "#c00000",
        },
    }
    profile.update(overrides)
    return profile


class RenderEmailTests(unittest.TestCase):
    def test_normalize_text_joins_hard_wrapped_paragraph_lines(self) -> None:
        source = "Dear Sam,\r\n\r\nThis paragraph was hard\r\nwrapped by a tool.\r\n"

        self.assertEqual(
            normalize_text(source),
            "Dear Sam,\n\nThis paragraph was hard wrapped by a tool.\n",
        )

    def test_escapes_dynamic_html_and_preserves_paragraphs(self) -> None:
        actual = render_html("Dear Sam,\n\n5 < 7 & 8 > 3")

        self.assertIn("<p>Dear Sam,</p>", actual)
        self.assertIn("<p>5 &lt; 7 &amp; 8 &gt; 3</p>", actual)
        self.assertNotIn("<script", actual)

    def test_renders_unordered_bullets_semantically(self) -> None:
        actual = render_html("Items:\n\n- One\n- Two")

        self.assertIn("<ul><li>One</li><li>Two</li></ul>", actual)

    def test_renders_ordered_bullets_semantically(self) -> None:
        actual = render_html("Steps:\n\n1. First\n2. Second")

        self.assertIn("<ol><li>First</li><li>Second</li></ol>", actual)

    def test_escapes_markup_inside_list_items(self) -> None:
        actual = render_html("- <strong>unsafe</strong>")

        self.assertIn("<li>&lt;strong&gt;unsafe&lt;/strong&gt;</li>", actual)
        self.assertNotIn("<strong>unsafe</strong>", actual)

    def test_signature_requires_exact_text_at_end(self) -> None:
        with self.assertRaisesRegex(ValueError, "signature does not match"):
            render_html("Body\n\nChanged signature", "Expected signature")

    def test_signature_uses_deliberate_breaks(self) -> None:
        signature = "Regards,\nExample Sender"

        actual = render_html(f"Body\n\n{signature}", signature)

        self.assertIn(
            '<div class="signature">Regards,<br>Example Sender</div>',
            actual,
        )

    def test_output_has_no_centering_fixed_width_script_or_remote_image(self) -> None:
        actual = render_html("Body")

        for forbidden in (
            "margin: 0 auto",
            "max-width",
            "<script",
            "<img",
            "text-align:center",
            "text-align: center",
        ):
            self.assertNotIn(forbidden, actual)

    def test_nul_byte_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "NUL"):
            render_html("Body\x00hidden")

    def test_cli_writes_utf8_html(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            text_path = root / "body.txt"
            output_path = root / "body.html"
            text_path.write_text("Dear Renée,\n\nHello.", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "render_email.py"),
                    "--text",
                    str(text_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Dear Renée,", output_path.read_text(encoding="utf-8"))


class StyledRenderTests(unittest.TestCase):
    def test_absent_style_keeps_output_free_of_inline_css(self) -> None:
        actual = render_html("Dear Sam,\n\nBody text.")

        self.assertNotIn("style=", actual)
        self.assertIn("<p>Body text.</p>", actual)

    def test_style_is_optional_and_does_not_change_unstyled_output(self) -> None:
        self.assertEqual(
            render_html("Dear Sam,\n\nBody text."),
            render_html("Dear Sam,\n\nBody text.", None, None),
        )

    def test_style_applies_base_typography_once_on_a_container(self) -> None:
        actual = render_html("Body text.", None, style_profile())

        self.assertIn("font-family:Helvetica, Arial, sans-serif", actual)
        self.assertIn("font-size:14px", actual)
        self.assertIn("line-height:1.55", actual)
        self.assertIn("color:#222222", actual)
        self.assertEqual(actual.count("font-family:Helvetica"), 1)

    def test_style_spaces_paragraphs_without_empty_elements(self) -> None:
        actual = render_html("First.\n\nSecond.", None, style_profile())

        self.assertIn("margin-top:16px", actual)
        self.assertNotIn("<p></p>", actual)

    def test_paragraph_list_style_avoids_list_elements(self) -> None:
        actual = render_html(
            "Items:\n\n- One\n- Two",
            None,
            style_profile(list_style="paragraph"),
        )

        self.assertNotIn("<ul>", actual)
        self.assertNotIn("<li>", actual)
        self.assertIn("One", actual)
        self.assertIn("Two", actual)

    def test_semantic_list_style_keeps_list_elements(self) -> None:
        actual = render_html("Items:\n\n- One\n- Two", None, style_profile())

        self.assertIn("<li>One</li>", actual)

    def test_pipe_table_renders_as_table_with_header(self) -> None:
        source = "| Record | Status |\n| --- | --- |\n| CI-1 | Posted |"

        actual = render_html(source, None, style_profile())

        self.assertIn("<table", actual)
        self.assertIn("<th", actual)
        self.assertIn(">Record<", actual)
        self.assertIn("<td", actual)
        self.assertIn(">CI-1<", actual)
        self.assertIn("border:1px solid #cccccc", actual)
        self.assertIn("padding:6px 10px", actual)

    def test_pipe_table_rows_are_not_joined_as_prose(self) -> None:
        source = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"

        actual = render_html(source, None, style_profile())

        self.assertEqual(actual.count("<tr>"), 3)

    def test_pipe_table_renders_without_a_style_profile(self) -> None:
        source = "| A | B |\n| --- | --- |\n| 1 | 2 |"

        actual = render_html(source)

        self.assertIn("<table>", actual)
        self.assertNotIn("style=", actual)

    def test_table_cells_escape_markup(self) -> None:
        source = "| Field |\n| --- |\n| <script>alert(1)</script> |"

        actual = render_html(source, None, style_profile())

        self.assertNotIn("<script", actual)
        self.assertIn("&lt;script&gt;", actual)

    def test_status_marker_colours_a_cell_and_is_removed(self) -> None:
        source = "| Record | Status |\n| --- | --- |\n| CI-1 | [!bad] Cancelled |"

        actual = render_html(source, None, style_profile())

        self.assertIn("color:#c00000", actual)
        self.assertIn("Cancelled", actual)
        self.assertNotIn("[!bad]", actual)

    def test_every_status_marker_maps_to_its_configured_colour(self) -> None:
        source = (
            "| A | B | C |\n| --- | --- | --- |\n"
            "| [!ok] Pass | [!warn] Partial | [!bad] Fail |"
        )

        actual = render_html(source, None, style_profile())

        self.assertIn("color:#1a7f37", actual)
        self.assertIn("color:#b36b00", actual)
        self.assertIn("color:#c00000", actual)

    def test_unknown_status_marker_stays_literal_text(self) -> None:
        source = "| Status |\n| --- |\n| [!bogus] Whatever |"

        actual = render_html(source, None, style_profile())

        self.assertIn("[!bogus] Whatever", actual)

    def test_status_marker_outside_a_table_stays_literal_text(self) -> None:
        actual = render_html("[!bad] Not a table cell.", None, style_profile())

        self.assertIn("[!bad] Not a table cell.", actual)

    def test_cell_content_cannot_escape_the_style_attribute(self) -> None:
        source = '| Field |\n| --- |\n| " onmouseover="alert(1) |'

        actual = render_html(source, None, style_profile())

        self.assertNotIn('onmouseover="alert(1)"', actual)
        self.assertIn("&quot;", actual)

    def test_styled_output_still_avoids_centering_and_fixed_width(self) -> None:
        source = "| A |\n| --- |\n| 1 |\n\nBody."

        actual = render_html(source, None, style_profile())

        for forbidden in (
            "margin: 0 auto",
            "max-width",
            "<script",
            "<img",
            "text-align:center",
            "text-align: center",
        ):
            self.assertNotIn(forbidden, actual)

    def test_styled_render_is_deterministic(self) -> None:
        source = "Dear Sam,\n\n| A | B |\n| --- | --- |\n| [!ok] 1 | 2 |\n\nRegards."

        self.assertEqual(
            render_html(source, None, style_profile()),
            render_html(source, None, style_profile()),
        )


if __name__ == "__main__":
    unittest.main()
