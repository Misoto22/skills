---
name: photo-abstract-editorial-native
description: Assemble a source-faithful photograph with a supplied editorial abstraction panel as a sharp comparison board, preserving orientation, aspect ratio, source provenance, and lower-panel scale. Use for original-versus-abstract photography diptychs, photo comparison cards, or repairing blurred and stretched editorial boards; not for generating lower artwork or replacing a separately licensed art-direction skill.
license: MIT
metadata:
  version: "0.9.2"
---

# Photo Abstract Editorial Native

Build a comparison board with the original photograph and separately supplied abstract artwork, without cropping, upscaling, blurring, or stretching either. Use the photograph above the artwork by default; use the portrait side-by-side exception only when it keeps a very tall source readable.

## 1. Establish the two inputs

Require both of these inputs before composing:

- `source`: the user-approved original photograph.
- `lower-art`: an abstract panel made from that photograph, supplied separately or created with a separately licensed skill.

Choose the strongest available source in this order: an explicit original file, a user-exported unmodified Photos original, a downloaded cloud original, then a derivative only when the user accepts that limitation. Record which one was used. Never silently substitute a preview or a derivative for an original.

Do not ask an image generator to recreate the photograph. Keep the source pixels in the source section; only apply auto-orientation and a downscale when needed.

## 2. Compose without distortion

Read [the composition contract](references/composition-contract.md) before laying out the board. It defines the output geometry and the checks that prevent the two known failures: a soft upper photo and a squashed lower panel.

Use a flat ivory artwork field. Centre the lower artwork with generous breathing room. Keep its native aspect ratio and never upscale it. Preserve any title that belongs to the supplied lower panel; do not invent labels, frames, watermarks, or extra decoration.

## 3. Audit before delivery

Create a small source manifest alongside the output. It must state the source path and type, original and output dimensions, orientation handling, lower-art dimensions, every resize operation, and confirmation that neither panel was upscaled or stretched.

Visually inspect at least one landscape and one portrait result in a batch. Reject and regenerate a board if the source photograph is visibly soft, either section is geometrically distorted, the source photo is altered, or the lower artwork loses its title or required whitespace.

## 4. Visual examples

The examples are real user-authorized boards produced during the native-resolution audit. They demonstrate the intended proportion-preserving result, not templates to reuse.

![Whale comparison board: sharp photograph above a centered abstract panel](assets/examples/whale-native-board.jpg)

![Harbour bridge comparison board: a wide source remains wide above its lower abstraction](assets/examples/harbour-bridge-native-board.jpg)

![Portrait side-by-side comparison board: a tall source is intact on the left and its lower abstraction remains intact on the right](assets/examples/portrait-native-board.jpg)

## 5. Attribution and scope

This is an independent composition and quality-assurance companion. It does not contain or reproduce the artistic-generation prompt from the upstream `photo-abstract-editorial` project. When the lower panel comes from [photo-abstract-editorial by ZzzLc0405](https://github.com/ZzzLc0405/photo-abstract-editorial), credit ZzzLc0405 and the requested attribution, **@AM.**, then read [the attribution and licence boundary](references/attribution.md) and comply with its terms.
