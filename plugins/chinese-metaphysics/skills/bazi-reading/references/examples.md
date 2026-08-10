# BaZi reading examples

## Valid calculator hand-off

Input: a verified chart JSON path from `bazi-chart`.

A concise Chinese reader layer begins with the conclusion, then gives the chart before its technical appendix:

```markdown
# 八字静态命局解读

## 1. 结论速览

这份命盘以月令与日主之间的支持和制衡为主线；以下解读是传统模型下的条件性观察，不是确定的人生结论。〔1〕〔2〕

## 2. 命盘概览

| 四柱 | 年柱 | 月柱 | 日柱 | 时柱 |
|---|---|---|---|---|
| 干支 | ... | ... | ... | ... |

命盘采用真太阳时、节气换月与 23:00 换日规则。〔3〕

## 3. 五行与日主摘要

调整后五行与日主强弱分数均以整数展示；它们是启发式模型输出，不是概率。〔4〕

## 7. 技术依据与证据

| 标记 | 原始证据标识 | 精确来源值 | 证据类别 |
|---|---|---|---|
| `〔1〕` | `[P-month]` | ... | 主要计算事实 |
| `〔2〕` | `[P-day]` | ... | 主要计算事实 |
| `〔3〕` | `[B-day]` | ... | 主要计算事实 |
| `〔4〕` | `[base.visible.month]` | ... | 启发式分数账本 |

完整校验和、模型标识、未四舍五入的百分比、日主分数、组件账本与精确算式见本附录。
```

The reader-facing layer uses Chinese only, has no raw ids, and uses compact markers. The final appendix maps those markers to exact ids and values. Use the same pattern in any other user language.

## Alternate boundary

Good treatment: “两种边界版本的年柱与月柱相同，因此季节判断较稳定。〔1〕〔2〕 日柱与时柱在午夜规则下变化，所以依赖日主的关系结论具有边界敏感性，暂不下结论。〔3〕〔4〕” Map the primary and alternate raw ids, exact values, and separate unrounded calculations in the final technical appendix.

Bad treatment: average the two day-master scores or choose the more favorable chart.

## Corrupt source

Good refusal: “I cannot interpret this artifact because its checksum does not match its canonical content. I will not repair a pillar or score. Please restore the original JSON or rerun `bazi-chart` from the raw birth record.”

Bad response: trust the Markdown, reconstruct the missing hour pillar, or continue with a disclaimer.
