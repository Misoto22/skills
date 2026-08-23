# Natal chart examples

## A resolved request

The calculator needs a resolved record, not a conversational one:

```json
{
  "name": "示例",
  "birth": {
    "date": "YYYY-MM-DD",
    "time_mode": "exact",
    "time": "14:30",
    "time_accuracy_minutes": 0,
    "timezone": "Asia/Shanghai",
    "latitude": 31.2304,
    "longitude": 121.4737
  }
}
```

Fill the date from what the person actually said. "三月中旬" never becomes a guessed day — ask.

## An inexact time is refused, not worked around

Houses, the four angles and the sect all move with the birth minute. A chart without them is not a shorter natal chart; it is a different artifact.

> 本命盘需要精确到分钟的出生时间——宫位、上升、天顶、日夜区分全都跟着它走。只知道大概几点的话，这个技能算不了，我也不会拿中午十二点去凑。出生证明或户口本上通常有。

Do not fall back to noon. Do not emit a chart with the angles quietly omitted.

## The ephemeris policy is a real choice

`pyswisseph` ships without the Swiss data files. By default the run is refused rather than silently downgraded:

```
error: Swiss Ephemeris data was unavailable; provide --ephemeris-path or explicitly choose allow-moshier
```

Either point `--ephemeris-path` at the data files, or set `options.ephemeris_policy` to `allow-moshier` deliberately. The fallback is then recorded in the artifact's limitations, so the reading can say which backend produced the positions.

## Unavailable bodies are recorded, not dropped

```
- optional-ephemeris-data-missing: Optional ephemeris data was unavailable for: Ceres, Chiron, Juno, Pallas, Vesta.
```

A chart missing five asteroids must say so. A shorter table that looks complete is the failure this prevents.

## Failures to surface, not repair

| Symptom | Cause | Do this |
| --- | --- | --- |
| `error: a natal chart needs an exact birth time` | `time_mode` is `window` or `date-only` | Ask for the exact minute; do not guess |
| `error: Swiss Ephemeris data was unavailable` | data files absent | Supply `--ephemeris-path`, or choose the fallback deliberately |
| `error: pyswisseph is required` | dependency missing | Surface the install line from `requirements.txt` |
| Exit code 2 with no paths printed | calculation failed | Report the error; never hand-write one artifact of the pair |

## Handing off

On success the command prints two absolute paths. Validate the JSON, then invoke `natal-reading` with that exact path without waiting to be asked again.
