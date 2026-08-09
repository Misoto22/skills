# Worked examples

The measurements below are synthetic and exist only to demonstrate evidence handling and workflow boundaries.

## 1. Direct reading of an existing file

**Asked**: Interpret `synastry_Person-A_Person-B.txt` and save the reading beside it.

**Source excerpt**:

```text
Person A Venus       trine             Person B Moon        0.42°
Person A Mercury     square            Person B Saturn      1.10°

Person B bodies falling in the houses of Person A
  Sun → H11

Person A bodies falling in the houses of Person B
  Jupiter → H2
```

**Reading excerpts**:

> The relationship signature combines emotional ease with a more effortful mental rhythm. Affection and emotional response may find an easy flow (Person A Venus trine Person B Moon, orb 0.42°), while serious conversations may alternate between expression and caution (Person A Mercury square Person B Saturn, orb 1.10°).
>
> The effects are not identical in both directions. Person B's Sun activates Person A's 11th house, so Person A may experience Person B through community, friendship, or shared aspirations. Person A's Jupiter activates Person B's 2nd house, which may expand Person B's confidence around values and resources. These directional overlays do not show that both people experience the same theme.
>
> `Friendship, community, and social networks` qualifies as an applied domain because the 11th-house overlay is reinforced by the relationship's personal-planet contacts. A money module would require another independent relevant contact before being added without a user request; the 2nd-house overlay alone is not enough.

**Wrote**: `synastry_reading_Person-A_Person-B.md`.

The prose distinguishes measurement from interpretation, preserves each orb, names overlay direction, and makes no forecast or score.

## 2. Automatic Chinese hand-off

**State**: `synastry` successfully wrote `charts/synastry_甲_乙.txt` with Chinese labels.

**Action**: Start this skill immediately with that exact path. Do not ask whether the user also wants a reading.

**Replied**:

> 原始合盘数据：`charts/synastry_甲_乙.txt`
>
> 分析报告：`charts/synastry_reading_甲_乙.md`
>
> 报告先分析关系主轴、双方感受差异、情绪安全、吸引与亲密、沟通、冲突修复、信任承诺和共同方向，再仅展开用户要求或证据充分的现实领域。每项解读都链接到原始相位、orb 或有方向的宫位互入。完整内容在 Markdown 文件中。

## 3. Missing optional ephemeris bodies

**Source**: Both natal blocks, the aspect table, and both overlay directions are present. The source also says Chiron, Ceres, Pallas, Juno, and Vesta were not resolved because an ephemeris data file was missing.

**Action**: Write the report. Under `Basis and limitations`, repeat the five unresolved bodies. Do not mention a Juno contact, Chiron theme, or asteroid absence as if it were a measured placement.

This is degraded coverage, not an incomplete core synastry file.

## 4. Incomplete source

**Asked**: Analyze an excerpt containing two natal charts and several aspects but no house overlays.

**Replied**:

> I cannot write the fixed reading from this excerpt. It is missing both required overlay sections: A's bodies in B's houses, and B's bodies in A's houses.
>
> Please provide the complete synastry data file or run the calculator again. I will not estimate the missing houses from the aspect list.

No Markdown file is written. A partial document with complete-looking headings would be easy to mistake for a complete reading.

## 5. Requested domain with weak evidence

**Asked**: Include daily home life and money in the applied section.

**Source pattern**: The complete file supports a domestic-life reading through two relevant Moon/Saturn contacts and a 4th-house overlay. It contains only one isolated 2nd-house overlay for money.

**Action**:

- Write the full domestic-life module with exact evidence and practical guidance.
- Keep the requested money heading, but use the `Evidence limit` form. State that one isolated overlay does not support a confident money-specific reading.
- Do not convert a general Venus aspect into financial advice unless its actual bodies, aspect, context, and supporting evidence make that implication relevant.

The user request controls whether the weak-evidence domain appears; it does not lower the standard for making claims inside it.
