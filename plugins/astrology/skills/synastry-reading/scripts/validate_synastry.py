#!/usr/bin/env python3
"""Validate a synastry v2 artifact and emit a deterministic evidence ledger."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from safe_output import (
    OutputExistsError,
    SourceIdentityError,
    matches_identity,
    write_atomic_bytes,
    write_stdout,
)
from synastry_schema import SCHEMA_VERSION, SchemaError, canonical_json, validate_artifact


@dataclass(frozen=True)
class EvidenceSubject:
    """One stable artifact subject ID available to the model ledger."""

    id: str


@dataclass(frozen=True)
class EvidenceItem:
    """One immutable, ownership-preserving measurement available to a reading."""

    id: str
    kind: str
    citation: str
    display: str
    data: Mapping[str, object] = field(compare=True, repr=False)


@dataclass(frozen=True)
class EvidenceLedger:
    """Validated source metadata and deterministically ordered reading evidence."""

    chart_id: str
    subjects: tuple[EvidenceSubject, ...]
    evidence: tuple[EvidenceItem, ...]
    language: str = "en"
    configuration: Mapping[str, object] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)
    limitations: tuple[Mapping[str, object], ...] = ()
    source_device: int | None = field(default=None, compare=False, repr=False)
    source_inode: int | None = field(default=None, compare=False, repr=False)
    source_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-ready ledger representation."""

        result = asdict(self)
        result.pop("source_device")
        result.pop("source_inode")
        provenance = result["provenance"]
        assert isinstance(provenance, dict)
        provenance.pop("data_path", None)
        return result


def load_ledger(path_or_payload: str | os.PathLike[str] | Mapping[str, object]) -> EvidenceLedger:
    """Validate one JSON artifact path or in-memory JSON object and normalize its evidence."""

    source_path: Path | None = None
    source_identity: tuple[int, int] | None = None
    if isinstance(path_or_payload, Mapping):
        payload: object = path_or_payload
    elif isinstance(path_or_payload, (str, os.PathLike)):
        source_path = Path(path_or_payload).expanduser()
        if source_path.suffix != ".json":
            raise ValueError("source must be a JSON object or a path ending in .json; TXT is not supported")
        payload, source_identity = _read_json_source(source_path)
    else:
        raise TypeError("source must be a JSON object or a path ending in .json")

    validated = validate_artifact(payload)  # type: ignore[arg-type]
    evidence = _evidence(validated)
    subjects = tuple(
        EvidenceSubject(id=str(subject["id"]))
        for subject in validated["subjects"]  # type: ignore[union-attr]
    )
    configuration = copy.deepcopy(validated["configuration"])
    language = str(configuration.get("language", "en"))  # type: ignore[union-attr]
    return EvidenceLedger(
        chart_id=str(validated["chart_id"]),
        subjects=subjects,
        evidence=evidence,
        language=language,
        configuration=configuration,  # type: ignore[arg-type]
        provenance=copy.deepcopy(validated["provenance"]),  # type: ignore[arg-type]
        limitations=tuple(copy.deepcopy(validated["limitations"])),  # type: ignore[arg-type]
        source_device=source_identity[0] if source_identity is not None else None,
        source_inode=source_identity[1] if source_identity is not None else None,
        source_digest=str(validated["integrity"]["digest"]),  # type: ignore[index]
        schema_version=str(validated["schema_version"]),
    )


def _read_json_source(source_path: Path) -> tuple[object, tuple[int, int]]:
    descriptor = os.open(source_path, os.O_RDONLY)
    stream = None
    try:
        status = os.fstat(descriptor)
        stream = os.fdopen(descriptor, encoding="utf-8")
        descriptor = -1
        return json.load(stream), (status.st_dev, status.st_ino)
    finally:
        if stream is not None:
            stream.close()
        elif descriptor >= 0:
            os.close(descriptor)


def _evidence(artifact: Mapping[str, object]) -> tuple[EvidenceItem, ...]:
    aspects = sorted(artifact["aspects"], key=canonical_json)  # type: ignore[arg-type]
    overlays = sorted(artifact["overlays"], key=canonical_json)  # type: ignore[arg-type]
    items = tuple(_aspect_item(item) for item in aspects) + tuple(_overlay_item(item) for item in overlays)
    identifiers = [item.id for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("evidence digest collision; the artifact cannot be cited unambiguously")
    return items


def _aspect_item(value: Mapping[str, object]) -> EvidenceItem:
    data = copy.deepcopy(dict(value))
    identifier = _evidence_id("aspect", data)
    source = str(data["source_subject_id"])
    target = str(data["target_subject_id"])
    certainty = str(data["certainty"])
    if certainty == "exact":
        measurement = f"orb {_number(data['orb_degrees'])}°"
    else:
        orb_range = data["orb_range_degrees"]
        assert isinstance(orb_range, Mapping)
        measurement = (
            f"orb range {_number(orb_range['minimum_degrees'])}°-{_number(orb_range['maximum_degrees'])}°"
        )
    display = (
        f"aspect: {source} {data['source_body']} -> {target} {data['target_body']}; "
        f"direction {source}->{target}; kind {data['kind']}; certainty {certainty}; {measurement}"
    )
    return EvidenceItem(identifier, "aspect", f"[{identifier}] {display}", display, data)


def _overlay_item(value: Mapping[str, object]) -> EvidenceItem:
    data = copy.deepcopy(dict(value))
    identifier = _evidence_id("overlay", data)
    source = str(data["source_subject_id"])
    target = str(data["target_subject_id"])
    display = (
        f"overlay: {source} {data['source_body']} -> {target} house {data['target_house']}; "
        f"direction {source}->{target}; certainty exact"
    )
    return EvidenceItem(identifier, "overlay", f"[{identifier}] {display}", display, data)


def _evidence_id(kind: str, data: Mapping[str, object]) -> str:
    digest = hashlib.sha256(canonical_json(data)).hexdigest()[:4].upper()
    return f"E-{kind.upper()}-{digest}"


def _number(value: object) -> str:
    return format(float(value), ".15g")


def source_identity(ledger: EvidenceLedger) -> tuple[int, int] | None:
    """Return the (device, inode) of the file the ledger was read from, if it came from one."""

    if ledger.source_device is None or ledger.source_inode is None:
        return None
    return ledger.source_device, ledger.source_inode


def is_source_path(path: Path, ledger: EvidenceLedger) -> bool:
    """Return whether path is the very file the ledger was read from."""

    return matches_identity(path, source_identity(ledger))


def ledger_bytes(ledger: EvidenceLedger) -> bytes:
    """Return the canonical ledger JSON exactly as it is written to disk."""

    return canonical_json(ledger.to_dict()) + b"\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="synastry v2 .json artifact, or - for a JSON object on stdin")
    parser.add_argument("--out", type=Path, help="write the normalized ledger to this JSON path")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing ledger atomically")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the source validator CLI and return zero or two."""

    arguments = _parser().parse_args(argv)
    try:
        source: str | Mapping[str, object] = arguments.source
        if source == "-":
            payload = json.load(sys.stdin)
            if not isinstance(payload, Mapping):
                raise TypeError("stdin source must be a JSON object")
            source = payload
        ledger = load_ledger(source)
    except json.JSONDecodeError:
        print("error: source is not valid JSON", file=sys.stderr)
        return 2
    except SchemaError:
        print("error: source JSON failed synastry v2 validation", file=sys.stderr)
        return 2
    except OSError:
        print("error: could not read source JSON", file=sys.stderr)
        return 2
    except (TypeError, ValueError):
        print("error: source must be a synastry v2 JSON object or .json file", file=sys.stderr)
        return 2

    if arguments.out is None:
        if write_stdout(canonical_json({"status": "valid"}) + b"\n"):
            return 0
        print("error: could not write ledger output", file=sys.stderr)
        return 2
    payload = ledger_bytes(ledger)
    try:
        if arguments.out.suffix != ".json":
            raise ValueError("ledger output must end in .json")
        if is_source_path(arguments.out, ledger):
            raise SourceIdentityError("ledger output must not replace the source JSON")
        write_atomic_bytes(
            payload,
            arguments.out,
            overwrite=arguments.overwrite,
            temporary_prefix="synastry-ledger",
            forbidden_identity=source_identity(ledger),
        )
        return 0
    except SourceIdentityError:
        print("error: ledger output must not replace the source JSON", file=sys.stderr)
    except OutputExistsError:
        print("error: ledger output already exists; use --overwrite", file=sys.stderr)
    except (OSError, TypeError, ValueError):
        print("error: could not write ledger output", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
