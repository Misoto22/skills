# Natal reading examples

## Accepting a hand-off

`natal-chart` prints two paths and invokes this skill with the JSON one. Validate before reading a single placement:

```bash
python3 scripts/validate_natal.py natal_<name>.json
```

It prints the evidence count on success and names the exact defect on failure. Never read from the Markdown alone — it is a rendering, not a machine source.

## Refusing a corrupt source

> 这份星盘的 checksum 与内容对不上，说明文件生成后被改动过。我不会在这个基础上解读——改过的宫位或度数会一路带偏结论。请用 `natal-chart` 重新算一次。

Name the exact defect. Do not patch the field, and do not read "most of it" with a caveat.

## Weighting by orb

Wrong — treats both as the same claim:

> 太阳与土星对分，太阳与天王星四分。

Right:

> 太阳与土星的对分相在 7 度多，是个宽相位——在这套传统里通常读作背景音而不是主线。真正紧的是月亮与金星的六分相，不到 0.7 度…（展开）

## A critical degree

Mercury at 29°39' of Scorpio is in the last degree of its sign:

> 水星落在天蝎座最后一度。这个位置对出生时间特别敏感：几分钟的误差就会让它换一个星座，整条与它相关的读法都会变。所以下面这段结论，是建立在你给的出生时间精确到分钟这个前提上的。

Say it where the claim is made, not only in the data card.

## A recorded limitation

> 这次排盘有五颗小行星（Ceres、Chiron、Juno、Pallas、Vesta）因为星历数据缺失没有算出来。这是**计算上的缺口**，不是你盘里没有它们。涉及这几颗的读法本报告不做。

Never let a missing body read as an absent one.

## Depth, not breadth

Wrong — a table wearing prose:

> 太阳天蝎九宫。月亮巨蟹五宫。水星天蝎九宫。金星处女七宫。火星摩羯十一宫…

Right — two or three developed:

> 上升双鱼，其古典主星木星落白羊二宫且逆行…（展开日常表现、反向条件、可观察迹象）

## Offering the poster

Only when asked:

> 要不要出一份水墨风的单页 HTML？可以截图或打印，内容与上面一致，审计明细仍在单独那份文件里。

Every recorded limitation goes on it. A poster that hides a missing body is a failed poster.
