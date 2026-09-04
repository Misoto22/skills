---
name: logo-banner
description: Create cohesive raster logo, app-icon, favicon, and repository-hero systems through ChatGPT Image when a user asks to design or refresh visual identity, a logo, a banner, branding assets, or light and dark brand variants; stop clearly when the host lacks that generator rather than substituting another tool; not for code-drawn SVG icons, general website layout, or ordinary photo retouching.
license: MIT
metadata:
  version: "0.12.0"
---

# Logo Banner

Create a small, coherent raster identity system through ChatGPT Image, from a
confirmed visual direction to approved project assets.

## When a request names several repositories

Treat every explicitly named repository as a separate identity system. Record
its exact path or URL, audience, existing visual language, asset location, and
approval state before creating a direction. If a name cannot be resolved to one
repository, ask; never widen the scope by searching an unspecified parent
directory.

Inspect, draft, generate, and check independent repositories concurrently when
the host supports concurrent work. Keep each repository's composition, copy,
assets, prompts, and approvals separate. A shared identity system exists only
when the user explicitly requests one after both repositories have been
inspected; otherwise, an approval or asset for one repository never authorizes
reuse or integration in another.

Give one combined handoff with a clearly labelled result for each repository:
asset paths, final prompt, visual checks, approval state, integration state, and
any remaining blocker. A completed identity system never stands in for the rest.

## Establish the direction first

1. Inspect the project before proposing a look. Identify its name, purpose,
   audience, existing visual language, primary surfaces, and any non-negotiable
   constraints. Do not invent product facts.
2. If a complete direction is not already supplied, offer exactly three compact,
   project-specific directions. Each must name a mood, palette, motif, and
   typographic character. Ask the user to select or amend one.
3. Restate the selected direction as a short art-direction brief covering the
   intended uses, light/dark support, palette, motifs, typography, exact copy,
   and explicit avoid list. Ask for confirmation before generating anything.
4. Treat an existing style preference as a proposed direction, not approval.
   Confirm it and the required assets before generation.

Do not make visualization or intensive questioning a gate. If a visualization
capability or GrillMe is installed, offer it as an optional way to compare
directions or resolve a genuinely open decision. Continue without either when
the user can choose a style directly.

## Generate only with ChatGPT Image

Before generating or promising an asset, verify that the current host exposes the
built-in ChatGPT Image generator. If it does not, explain that this skill needs
that capability and stop. Do not claim that an image was generated, substitute
another generator, or offer an SVG, code-drawn, or stock-asset fallback.

Use the built-in ChatGPT Image generator for every logo, mark, app icon,
favicon source, banner, pattern, or in-image wordmark. Never replace it with
SVG, Canvas, HTML, CSS, Mermaid, manually drawn shapes, a stock asset, or a
different image generator.

- Start from a composition that is simple enough to survive a 32 px browser tab.
  A favicon or app icon uses the distinctive symbol alone, never a full wordmark.
- Write a production prompt that names the use case, visual direction, palette,
  placement, exact text, and constraints. When text is required, quote it
  verbatim and require it to be legible and correctly spelled.
- For a revision, provide the current raster as the edit target and list the
  invariants. Change only the requested region or property.
- Build a dark variant by editing the approved light composition, or vice versa.
  Lock the layout, scale, motifs, copy, and hierarchy; change only the surface,
  contrast, and palette needed for the second appearance.
- Iterate with one targeted change at a time. If ChatGPT Image cannot reproduce
  critical in-image text faithfully after two focused edits, show the drafts and
  ask for direction. Do not create a code or SVG workaround.
- Use ordinary raster cropping or resizing only to derive delivery sizes from an
  approved generated raster. Do not use code to draw, trace, or typeset a mark.

## Deliver a usable system

Match the asset list to the request. When a complete repository identity is
requested, propose this compact pack before producing it:

- full logo concept for presentations and references;
- app-icon master and a 512 px app icon;
- 32 px favicon that remains recognizable at tab size;
- light and dark social/README Hero banners when the project supports both;
- optional low-contrast background pattern.

Keep the same asset family across every output: one core symbol, restrained
palette, compatible texture, and consistent type treatment. Reserve open space
in a social banner for copy. Put bilingual copy on separate lines, preserve it
exactly across themes, and keep it away from the symbol and crop edges.

## Inspect and integrate

1. Inspect every generated result at full size. Inspect icons again at their
   intended small size. Check silhouette, contrast, edge quality, exact text,
   and absence of watermarks or unintended objects.
2. Compare light and dark banners side by side. Reject any pair whose composition
   or wording diverges rather than merely adapting its contrast.
3. Present the selected generated assets and ask for explicit approval before
   integration. Style confirmation and a pre-generation request such as “put it
   in the README” do not count as approval of the generated output. Do not
   replace project assets, edit a README, or publish changes until the user gives
   that separate approval.
4. Save explicitly approved raster files in the project's established asset location; use
   `assets/brand/` only when the project has no better convention. Record each
   asset's intended use and palette in a short asset guide.
5. When asked to use a Hero in a README, use a `<picture>` element so light and
   dark banners switch by `prefers-color-scheme`. Keep the README title only when
   it adds information that the Hero does not already carry.
6. Report the saved asset paths, the final ChatGPT Image prompt or prompts, and
   the visual checks performed. Follow the repository's normal validation and
   publishing process only when the user asks to ship the changes.
