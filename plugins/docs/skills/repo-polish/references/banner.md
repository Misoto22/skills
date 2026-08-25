# Banner

The hero image is the only piece of visual design GitHub will render for you, and the first thing anyone sees. It is also the element most likely to be broken, and a broken one is louder than no image at all.

## Rules

**Commit the asset.** `assets/hero-light.svg`, or wherever the repository already keeps images. A hotlinked banner — a design tool's share URL, a CDN, someone's blog — is an outage the repository owner does not control and cannot see. It also leaks a referrer for every visitor.

**Serve both themes.** GitHub renders the README against the reader's own theme, and a banner tuned for one is unreadable in the other. `<picture>` with a `prefers-color-scheme` source is the only mechanism that works:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img alt="[project]" src="assets/hero-light.svg" width="820">
</picture>
```

The `<img>` is the light variant and the fallback both. A renderer that ignores `<picture>` still shows something.

**SVG over PNG.** It stays sharp on every display, it diffs as text so a colour change is reviewable, and it is usually smaller. Where the artwork is photographic, PNG at 2× the display width, and keep it under a few hundred kilobytes — the README is often the first request a phone makes.

**Set `width`, never `height`.** A width around 820 fills GitHub's content column without overflowing it. Height set alone distorts nothing but guarantees a layout shift while the asset loads.

**Write a real `alt`.** It is what a screen reader announces and what shows when the asset 404s. The project name and what it is — not "banner", not "logo", not the filename.

## Text inside an SVG

GitHub sanitises SVG and its renderer honours less than a browser does.

- **Place text at explicit coordinates and left-anchor it.** `text-anchor="middle"` is not honoured everywhere, and a centred label that falls back to left-anchored is clipped at the edge. Compute the position yourself.
- **No external fonts.** `@font-face`, a Google Fonts `@import`, a `<link>` — none of them load. Name a system stack (`system-ui, -apple-system, "Segoe UI", sans-serif`), or convert the text to paths, which is what a wordmark should do anyway.
- **No scripts, no external references.** Both are stripped.
- **Check the sanitised output, not the source file.** Open the raw URL on GitHub and look at what came back.

## Sizing and safe area

- Keep the important content inside the middle 80% horizontally. Narrow viewports scale the whole image down rather than cropping, but the padding is what keeps a wordmark from touching the frame.
- Aspect ratio between about 3:1 and 4:1. Taller than that and the banner alone is the first screen, which pushes the sentence and the badges below the fold.
- Test at a phone width. Text sized for a desktop banner is unreadable at 380 pixels wide, and most first views of a README are on a phone.

## When there is no asset

Drop the `<img>` and the `<br />` after it. Never leave a placeholder in `src` — it does not read as a note to the author, it renders as a broken-image icon at the top of the page.

The centred block still works without it, and is better than a placeholder graphic. A CLI tool may reasonably open with a fenced sample of its own output instead — one screen, real output, no prompt characters.

Where the artwork needs to be designed rather than laid out, that is a separate job: a logo and banner system, light and dark, is brand work. This pass wires up the `<picture>` block, sizes it, and verifies it renders.

## Badges, below the banner

One badge per primary technology, version pinned in the label, official brand colour, `logoColor` set for contrast:

```
https://img.shields.io/badge/<Name>_<Version>-<hex>?logo=<slug>&logoColor=<fff|000>
```

Use `logoColor=000` on light brand colours (React `61DAFB`, Tailwind `06B6D4`), `fff` on dark ones. Underscores render as spaces. Look the slug up at [simpleicons.org](https://simpleicons.org).

No badges for build status, download counts, licence, "PRs welcome", or code style. They are noise on a personal or single-maintainer repository, and the CI section already says what runs.

## Verify

Open the rendered page and confirm the `<img>` reports a non-zero `naturalWidth` — that the file exists on disk is not the same check. Then switch themes and look again.
