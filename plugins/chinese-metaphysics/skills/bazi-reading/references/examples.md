# BaZi reading examples

## Valid calculator hand-off

Input: a verified chart JSON path from `bazi-chart`.

Write a Chinese reader report without evidence markers or technical identifiers:

```markdown
# 八字静态命局解读

## 你的命局主线

这份命盘的主线是：你更容易在有清晰方向时投入，也需要留出调整节奏的空间。这个判断来自传统命理模型，用来帮助观察，不是对人生的定论。

## 命盘倾向

| 四柱 | 年柱 | 月柱 | 日柱 | 时柱 |
|---|---|---|---|---|
| 干支 | … | … | … | … |

## 优势与张力

当你把想法落实为具体步骤时，往往更能发挥优势；压力较大时，也值得先分清是需要行动，还是需要恢复余地。

## 关系、工作与自我观察

1. 最近的选择里，哪些是在清晰目标下更有力量，哪些是在被催促时变得紧绷？
2. 下次想推动一件事前，先给自己一个可以调整的时间点，观察效率有没有改变。

## 模型数据卡

五行分布与日主参考分数是模型参考，不是概率。

[查看计算依据](bazi_reading_evidence_示例.md)
```

Write `bazi_reading_evidence_<name>.md` separately. It records the checksum, raw evidence ids, time basis, exact values, score ledger, and a heading-based map for each reader-report claim. It is not appended to the reader report.

## Alternate boundary

Good treatment: “两种边界版本的年柱与月柱相同，因此季节判断较稳定；日柱与时柱在午夜规则下变化，所以依赖日主的关系结论暂不下结论。” Put the primary and alternate raw ids, exact values, and separate unrounded calculations in the evidence artifact.

Bad treatment: average the two day-master scores or choose the more favorable chart.

## Corrupt source

Good refusal: “I cannot interpret this artifact because its checksum does not match its canonical content. I will not repair a pillar or score. Please restore the original JSON or rerun `bazi-chart` from the raw birth record.”

Bad response: trust the Markdown, reconstruct the missing hour pillar, or continue with a disclaimer.
