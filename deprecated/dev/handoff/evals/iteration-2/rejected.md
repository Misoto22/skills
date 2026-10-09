# Rejected edits

None. All three diagnostic corrections passed the clean comparison gate:
tuning improved from 6/9 to 9/9 and holdout remained 3/3.

## Discarded comparison

The first final holdout measurement ran while an unrelated runtime regression
fix was dirty. Its 3/3 score remains recorded but cannot pair with the clean
tuning provenance. A fresh holdout from the exact clean candidate commit also
passed 3/3 and is the only holdout used by this iteration's benchmark. No run
was rewritten, and no instruction was tuned to the holdout.
