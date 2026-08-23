# Zi Wei chart examples

## A resolved request

The placer needs a resolved record, not a conversational one. "某年三月中旬
早上八点半，上海" becomes a request whose every field is exact:

```json
{
  "name": "示例",
  "birth_place": "上海, 中国",
  "birth_date": "YYYY-MM-DD",
  "birth_time": "08:30",
  "calendar": "gregorian",
  "timezone": "Asia/Shanghai",
  "latitude": 31.2304,
  "longitude": 121.4737,
  "gender": "female"
}
```

Fill the date from what the person actually said. A conversational "三月中旬"
never becomes a guessed day — ask.

## Gender is asked for, never inferred

A decade cycle runs forward for a yang-year male or a yin-year female, and
backward for the other two combinations. There is no neutral default that
produces a correct chart.

> 紫微的大限方向由年干阴阳配合性别决定，所以这一步需要你直接告诉我：male 还是
> female？我不会从名字或称呼推断。

If the person declines, say the decade ranges cannot be produced and stop. Do
not place the chart without them and do not pick a direction to keep going.

## A late-zi birth produces two charts

`23:30` is not a rounding problem. Under the 23:00 boundary the lunar day
advances, and the lunar day is what places 紫微 — so the whole chart moves.

```
primary   (23:00 boundary)  lunar 1985年4月23日   紫微 in 午
alternate (00:00 boundary)  lunar 1985年4月22日   紫微 in 酉
```

Hand both to `ziwei-reading` and let it separate the stable findings from the
ones the boundary decides. Never average the two, and never pick the more
flattering chart.

## The year pillar will not match the BaZi chart, sometimes

A birth in the window between lunar new year and Li Chun carries one year stem
in Zi Wei and the previous one in BaZi. Both are correct within their own system:
Zi Wei turned the year at lunar new year, BaZi has not turned it yet.

Report it as a recorded difference. Do not "fix" either chart, and do not let a
cross-reading quietly adopt one year stem for both systems.

## Failures to surface, not repair

| Symptom | Cause | Do this |
| --- | --- | --- |
| `error: gender: Zi Wei decade cycles are direction-dependent…` | gender missing or not `male`/`female` | Ask for it; do not guess |
| `error: pyswisseph is required…` | dependency missing | Surface the install line from `requirements.txt`; never substitute an approximate lunar table |
| `error: lunar 2020 month 4 does not exist` | leap flag wrong for a lunar input | Confirm 闰四月 vs 四月 with the person |
| `error: birth_time: expected HH:MM…` | hour-only or approximate time | Refuse; the hour branch moves both palaces |
| Exit code 2 with no paths printed | placement failed | Report the error; never hand-write one artifact of the pair |

## Handing off

On success the command prints two absolute paths. Validate the JSON, then invoke
`ziwei-reading` with that exact path without waiting to be asked again.
