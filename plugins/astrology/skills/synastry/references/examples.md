# Worked examples

Three cases: a straight run with its automatic reading hand-off, a refusal, and
a Chinese run where the ephemeris was missing an optional data file. Every raw
data excerpt below is copied from a real run of
[request.example.json](request.example.json), not reconstructed.

## Contents

1. Straight run — two complete sets of birth details
2. Refusal — a birth time given to the hour
3. Chinese output — tighter minor orb, and a body the ephemeris could not resolve

---

## 1. Straight run — two complete sets of birth details

**Asked**: Run a synastry for Person A (1990-03-14 07:42, Shanghai) and Person B (1988-11-02 21:05, New York).

**Reading**: Both times carry minutes, both places resolve to a zone and a coordinate. Nothing blocks the run.

Coordinates and zones are looked up rather than recalled, and stated in the reply so a wrong one is visible. New York in early November 1988 is standard time, which the zone database resolves from the date — `utc_offset_hours` stays out of the request.

**Request**, written to `request.json`:

```json
{
  "people": [
    {
      "name": "Person A",
      "date": "1990-03-14",
      "time": "07:42",
      "timezone": "Asia/Shanghai",
      "latitude": 31.23,
      "longitude": 121.47,
      "birth_place": "Shanghai",
      "residence": "Shanghai"
    },
    {
      "name": "Person B",
      "date": "1988-11-02",
      "time": "21:05",
      "timezone": "America/New_York",
      "latitude": 40.71,
      "longitude": -74.01,
      "birth_place": "New York",
      "residence": "Shanghai"
    }
  ]
}
```

**Run**:

```bash
python3 scripts/compute_synastry.py --request request.json --out .
```

```
wrote ./synastry_Person-A_Person-B.txt
```

**Written** — the natal block opens with what was supplied and what it resolved to:

```
■ Birth data
  Local birth time    1990-03-14 07:42
  Birth place         Shanghai
  Current residence   Shanghai
  Time zone           Asia/Shanghai
  UTC offset          +8.00 h
  Coordinates         31.2300, 121.4700

■ Big three
  Sun           Pisces ♓ 23°08'       H12
  Moon          Libra ♎ 21°38'        H6
  Ascendant     Aries ♈ 26°31'        H1
```

and the synastry block sorts every cross-chart contact by orb:

```
■ Cross-chart aspects, tightest orb first
  Ptolemaic aspects within 8.0°, minor aspects within 3.0°.

  Person A Body       Aspect            Person B Body       Orb
  ------------------------------------------------------------------
  Venus               semi-sextile      Neptune              0.12°
  North Node          semi-square       Midheaven            0.13°
  Saturn              biquintile        Moon                 0.18°
  Neptune             sesquiquadrate    Moon                 0.22°
  Mercury             biquintile        Mercury              0.25°
```

**Hand-off**: The completed file is passed immediately to `synastry-reading`, which writes `synastry_reading_Person-A_Person-B.md` beside it.

**Replied after the hand-off**:

> Raw synastry data: `synastry_Person-A_Person-B.txt`.
>
> Reading: `synastry_reading_Person-A_Person-B.md`.
>
> The report covers love, friendship, business partnership, and money, with each interpretation linked to the exact source aspect, orb, or directional house overlay. Both coordinates are city centres, so each Ascendant carries a few arc-minutes of uncertainty; New York in November 1988 resolved to UTC−5.
>
> Say the word if you want any of it read.

**Note**: the `.txt` file remains measurement data. The model does not add a reading to that artifact or wait for another request; it delegates interpretation to the second skill and returns both paths.

---

## 2. Refusal — a birth time given to the hour

**Asked**: Compare our charts — I was born 1990-03-14 around 7am in Shanghai, he was born 1988-11-02 at 21:05 in New York.

**Reading**: One time is exact, the other is "around 7am". The Ascendant moves 15° an hour, so "around 7" spans most of a sign. Nothing is computed.

**Replied**:

> I need the first birth time to the minute before I can run this.
>
> The Ascendant moves one degree every four minutes, so "around 7am" leaves it anywhere from late Aries to early Taurus — which changes the house cusps, and with them every house overlay in the synastry. The second time is fine.
>
> A birth certificate or a hospital record usually carries it.

**Note**: no noon substitute, no early-and-late pair, and no partial run offering "the aspects that do not depend on the Ascendant". A half-computed chart invites exactly the reading it cannot support. The script refuses the same request for the same reason, so working around it here only moves the failure downstream.

No data file exists, so `synastry-reading` is not invoked and no Markdown report is written.

---

## 3. Chinese output — tighter minor orb, and an unresolved body

**Asked**: 帮我和他合个盘，标签用中文，次相位收紧一点

**Reading**: Same two people and the same request file. Only the flags change.

**Run**:

```bash
python3 scripts/compute_synastry.py --request request.json --out . --language zh --minor-orb 1.5
```

**Written**:

```
■ 合盘相位 · 按 orb 由紧到松
  主相位容许 8.0°、次相位容许 1.5°。

  Person A 天体       相位              Person B 天体       orb
  ------------------------------------------------------------------
  金星                十二分相          海王星               0.12°
  北交点              半刑              天顶                 0.13°
  土星                倍五分相          月亮                 0.18°
```

This installation had `pyswisseph` but not the asteroid data file, so five bodies were dropped and the report names them:

```
■ 小行星与敏感点
  ⚸ 莉莉丝        天蝎 ♏ 14°28'        7 宫
  ☊ 北交点        水瓶 ♒ 14°39'       11 宫
  ☋ 南交点        狮子 ♌ 14°39'        5 宫
    宿命点        天秤 ♎ 11°38'        6 宫
    东方点        白羊 ♈ 19°50'       12 宫
  未能解析 · 缺少星历数据文件: 凯龙星、谷神星、智神星、婚神星、灶神星
```

**Hand-off**: The completed Chinese data file is passed immediately to `synastry-reading`. The missing bodies remain explicit input limitations rather than placements to infer.

**Replied after the hand-off**:

> 原始合盘数据：`synastry_Person-A_Person-B.txt`，标签中文，次相位收到 1.5°。
>
> 分析报告：`synastry_reading_Person-A_Person-B.md`。
>
> 报告按爱情、友情、事业合作和金钱四个维度展开，并逐条引用原始数据。有一件事要说明：这台机器缺小行星星历文件，凯龙、谷神、智神、婚神、灶神五颗没算出来；数据文件和分析报告都明确保留了这个限制。这不是“没有相位”，而是“没有计算”。

**Note**: the missing bodies get their own paragraph rather than a footnote. The reading skill may continue because both natal blocks, the aspect table, and both overlay directions are complete, but it cannot make a claim involving any unresolved body.
