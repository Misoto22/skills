# BaZi chart workflow examples

## Complete Gregorian request

Resolve `DISPLAY_NAME, <YYYY-MM-DD>, <HH:MM>, CITY` to one city, decimal coordinates, and its historical IANA zone. Preserve the display name, declared place, and exact minute. Run the calculator and pass the resulting JSON path directly to `bazi-reading`.

## Lunar request

For `农历 <YYYY-MM-DD> <HH:MM>`, require the user to say whether the named lunar month is leap or ordinary. Store that decision as a Boolean `leap_month`; do not infer it from the year.

## True-solar Zi-hour alternate

If civil time becomes `23:xx` after longitude and equation-of-time corrections, the output contains a primary 23:00-boundary chart and a 00:00-boundary alternate. Preserve both complete calculations. The reading must describe which claims change between them.

## Refusals

- `around seven`: request the exact minute and do not run.
- `Springfield`: request the region/country when lookup is ambiguous.
- nonexistent DST wall time: explain that the stated local time did not occur and request documentary clarification.
- existing `bazi_NAME.json`: verify and route to `bazi-reading`; do not calculate again.
