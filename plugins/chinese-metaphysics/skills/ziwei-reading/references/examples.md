# Zi Wei reading examples

## Accepting a hand-off

`ziwei-chart` prints two paths and invokes this skill with the JSON one. Validate
before reading a single star:

```
schema  chinese-metaphysics.ziwei-chart, version 1   ✓
checksum matches canonical content                    ✓
twelve palaces, life and body both marked             ✓
four transformations, none naming an unplaced star    ✓
twelve decades, one direction                         ✓
```

Then build the evidence ledger, then write. Never read from the Markdown alone —
it is a rendering, not a machine source.

## Refusing a corrupt source

> 这份命盘的 checksum 与内容对不上，说明文件在生成后被改动过。我不会在这个基础上
> 解读，因为改动过的宫位会一路带偏结论。请用 `ziwei-chart` 重新排一次盘。

Name the exact defect. Do not patch the field, do not infer the missing palace,
and do not read "most of it" while noting a caveat.

## Handling a late-zi alternate

The alternate is not a rounding detail — the lunar day moves, so 紫微 moves:

```
primary   紫微 in 午, life palace 巳, bureau 金四局
alternate 紫微 in 酉, life palace 巳, bureau 金四局
```

Write three separated groups:

- **Both charts support**: the life palace branch and the bureau, so anything
  resting on those stands.
- **The boundary decides**: which star sits with 紫微 and therefore the whole
  main-star arrangement.
- **Withheld**: any conclusion that depended on the 紫微 group.

Lower the report's confidence explicitly. Do not average, and do not quietly
prefer the reading that sounds better.

## An unplaced transformation

戊 year transformations include 右弼化科. This release places 右弼, so nothing is
missing. But when a transformation names a star outside the placed set, say:

> 这一颗四化的落点本次排盘没有安到对应星曜，所以这条印记在这份报告里是**缺算**，
> 不是**没有**。判断时不要把它当作这个宫位安静。

## Depth, not breadth

Wrong — a table pretending to be a reading:

> 命宫天同化忌。兄弟宫破军。夫妻宫右弼擎羊。子女宫廉贞文曲禄存。财帛宫天钺陀罗。

Right — two or three palaces developed:

> 命宫天同庙而带化忌，在这套模型里常被读作：本性偏向温和与调和，但注意力会持续
> 落在「怎么让事情顺过去」这件事上，于是摩擦也集中在这里…（继续展开日常表现、
> 反向条件、可观察的迹象）

## Offering the poster

Only when asked:

> 要不要顺手出一份水墨风的单页 HTML？可以截图或打印，内容和上面这份报告一致，
> 审计明细仍然在单独那份文件里。

If yes, write the payload as data and run the renderer. Never hand-write the HTML.
