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

> Affection and emotional response may find an easy rhythm here (Person A Venus trine Person B Moon, orb 0.42°). The same relationship can require deliberate pacing in serious conversations, because enthusiasm may meet caution or correction (Person A Mercury square Person B Saturn, orb 1.10°).
>
> Friendship has a visible place in the bond: Person B's Sun falls in Person A's 11th house. In shared finances, Person A's Jupiter falling in Person B's 2nd house can amplify confidence around resources; that is a reason to agree limits, not evidence that an investment will succeed.

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
> 报告按照爱情、友情、事业合作和金钱四个维度展开，每一项解读都链接到原始相位、orb 或有方向的宫位互入。完整内容在 Markdown 文件中。

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
