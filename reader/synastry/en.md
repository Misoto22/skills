`synastry` computes; it does not interpret. What it is built around is treating uncertainty as a first-class value.

## An uncertain birth time is recorded as uncertain

A birth time that is unknown, or known only to the hour, is represented as a bounded window rather than collapsed to a midpoint that pretends to precision.

The reason is that a midpoint makes the uncertainty disappear into the number. Once "sometime in the afternoon" has been written down as 14:00, every later conclusion that rests on the ascendant and the houses looks exactly as reliable as one from an exact time. Keeping the window in the file is what lets the reading step know which conclusions to soften.

## The result can be checked

The calculation is written as a JSON v2 file recording which ephemeris backend produced it and at which version. The same birth details differ by seconds between backends, and without that record there is no way to explain why two runs disagree.

## Privacy-minimal by default

Full birth information is retained only when archival mode is asked for. By default the file keeps what the calculation needs rather than what identifies a person.

## It hands off when it is done

When the calculation finishes it hands the file to the reading skill. The boundary is deliberate: a calculation can be checked, an interpretation shifts with context, and putting both in one artefact drags the first one's credibility down to the second's.

## What it does not do

It does not interpret, does not read the legacy TXT format, does not compute a single-person natal chart, and produces no transits, forecasts, or compatibility score.
