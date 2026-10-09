"""The v2 contract's identity: its schema version and the profiles it names.

Declared here and nowhere else. The request parser, the synastry artifact schema
and the natal calculator all import these: an artifact echoes the profiles its
request named, so a second copy would let the writer and the validator disagree
the first time one of them moved.
"""

SCHEMA_VERSION = "2.0"
CALCULATION_PROFILE = "western-tropical-v1"
ASPECT_PROFILE = "ptolemaic-minor-v1"
DERIVED_PROFILE = "classical-derived-v1"
EVIDENCE_POLICY = "editorial-v1"
