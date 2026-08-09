# BaZi scoring model v1

`bazi-score-v1` is a transparent heuristic model. Its percentages and 0-100 day-master score are neither probabilities nor measurements endorsed by a calendar authority or ephemeris provider.

## Element distributions

The base distribution counts every visible stem and every hidden stem before normalization. Visible positions use weights of 1.0, 1.2, 1.2, and 1.0 from year through hour. Branch weights are 0.8, 1.4, 1.0, and 0.8. A branch with one hidden stem assigns it 100%; two hidden stems receive 70% and 30%; three receive 60%, 25%, and 15% in the declared order.

The adjusted distribution applies the month-command multiplier to those raw totals: prosperous 1.40, ministerial 1.20, resting 1.00, imprisoned 0.80, and dead 0.60. A successfully formed transformation adds 0.35 raw units to its declared element. A candidate transformation adds zero. The ledger records every input and adjustment before either distribution is normalized to 100%.

## Day-master strength

Strength starts at 50 and records separate seasonal, root, visible-support, control, production, drainage, and structural components. Month, day, hour, and year roots have different declared weights. Visible peers and resources add support; controlling pressure, output, and wealth load subtract it. Only fully formed transformations affect the structural component. The total is clamped only once at 0 or 100, and the output records a clamp when one occurs.

Scores up to 35 are labelled weak, scores from 65 are labelled strong, and values between them are labelled balanced. These labels summarize this model; they do not establish a special or following structure. Such a structure requires a separately declared rule with all prerequisites satisfied. Version 1 deliberately declares none.

## Confidence and alternate charts

Unresolved transformation candidates lower structural confidence. A chart calculator may lower confidence further when it emits a 00:00-boundary alternate. The primary and alternate must be scored independently; their values must never be averaged into a fabricated single chart.
