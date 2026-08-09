#!/usr/bin/env python3
"""Validate a synastry v2 artifact and emit a deterministic evidence ledger."""

from __future__ import annotations

import argparse
import copy
import ctypes
import errno
import hashlib
import json
import os
import secrets
import sys
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from synastry_schema import SchemaError, canonical_json, validate_artifact


class SourceIdentityError(ValueError):
    """An output path names the opened source artifact."""


class OutputExistsError(FileExistsError):
    """An exclusive output destination already exists."""


@dataclass(frozen=True)
class EvidenceSubject:
    """One presentation label bound to a stable artifact subject ID."""

    id: str
    display_name: str


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
    source_path: str | None = None
    source_device: int | None = field(default=None, compare=False, repr=False)
    source_inode: int | None = field(default=None, compare=False, repr=False)
    source_digest: str = ""
    schema_version: str = "2.0"

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-ready ledger representation."""

        result = asdict(self)
        result.pop("source_device")
        result.pop("source_inode")
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
        EvidenceSubject(
            id=str(subject["id"]),
            display_name=str(subject.get("display_name") or subject["id"]),
        )
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
        source_path=str(source_path.absolute()) if source_path is not None else None,
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


def _write_atomic_bytes(
    payload: bytes,
    destination: Path,
    *,
    overwrite: bool,
    temporary_prefix: str,
    forbidden_identity: tuple[int, int] | None = None,
) -> Path:
    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        for _ in range(32):
            candidate = destination.parent / f".{temporary_prefix}-{secrets.token_hex(8)}.tmp"
            try:
                descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            break
        if descriptor is None or temporary is None:
            raise FileExistsError(errno.EEXIST, "could not allocate an exclusive temporary file")

        descriptor_chmod = getattr(os, "fchmod", None)
        if descriptor_chmod is not None:
            descriptor_chmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError("could not complete file write")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None

        existing_identity = _path_identity(destination)
        if forbidden_identity is not None and existing_identity == forbidden_identity:
            raise SourceIdentityError("output must not replace the source JSON")

        if overwrite:
            if existing_identity is None:
                try:
                    os.link(temporary, destination)
                except FileExistsError as error:
                    raise OSError(errno.EBUSY, "output changed during installation") from error
                temporary.unlink()
                temporary = None
            else:
                _exchange_paths(temporary, destination)
                displaced_identity = _path_identity(temporary)
                if displaced_identity != existing_identity or (
                    forbidden_identity is not None and displaced_identity == forbidden_identity
                ):
                    _exchange_paths(temporary, destination)
                    if displaced_identity == forbidden_identity:
                        raise SourceIdentityError("output must not replace the source JSON")
                    raise OSError(errno.EBUSY, "output changed during installation")
                temporary.unlink()
                temporary = None
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError as error:
                raise OutputExistsError(
                    errno.EEXIST,
                    f"output already exists: {destination}",
                    destination,
                ) from error
            temporary.unlink()
            temporary = None
        return destination
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            with suppress(FileNotFoundError):
                temporary.unlink()


def _exchange_paths(first: Path, second: Path) -> None:
    """Atomically exchange two directory entries or fail closed."""

    library = ctypes.CDLL(None, use_errno=True)
    encoded_first = os.fsencode(first)
    encoded_second = os.fsencode(second)
    if sys.platform == "darwin":
        operation = getattr(library, "renameatx_np", None)
        if operation is None:
            raise OSError(errno.ENOTSUP, "atomic path exchange is unavailable")
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(-2, encoded_first, -2, encoded_second, 0x00000002)
    elif sys.platform.startswith("linux"):
        operation = getattr(library, "renameat2", None)
        if operation is None:
            raise OSError(errno.ENOTSUP, "atomic path exchange is unavailable")
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(-100, encoded_first, -100, encoded_second, 0x00000002)
    else:
        raise OSError(errno.ENOTSUP, "atomic path exchange is unavailable")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _path_identity(path: Path) -> tuple[int, int] | None:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY)
        status = os.fstat(descriptor)
        return status.st_dev, status.st_ino
    except OSError:
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _source_identity(ledger: EvidenceLedger) -> tuple[int, int] | None:
    if ledger.source_device is None or ledger.source_inode is None:
        return None
    return ledger.source_device, ledger.source_inode


def _is_source_path(path: Path, ledger: EvidenceLedger) -> bool:
    identity = _source_identity(ledger)
    return identity is not None and _path_identity(path) == identity


def _ledger_bytes(ledger: EvidenceLedger) -> bytes:
    return canonical_json(ledger.to_dict()) + b"\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="validated synastry v2 .json artifact")
    parser.add_argument("--out", type=Path, help="write the normalized ledger to this JSON path")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing ledger atomically")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the source validator CLI and return zero or two."""

    arguments = _parser().parse_args(argv)
    try:
        ledger = load_ledger(arguments.source)
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

    payload = _ledger_bytes(ledger)
    if arguments.out is None:
        try:
            sys.stdout.write(payload.decode("utf-8"))
            return 0
        except OSError:
            print("error: could not write ledger output", file=sys.stderr)
            return 2
    try:
        if arguments.out.suffix != ".json":
            raise ValueError("ledger output must end in .json")
        if _is_source_path(arguments.out, ledger):
            raise SourceIdentityError("ledger output must not replace the source JSON")
        _write_atomic_bytes(
            payload,
            arguments.out,
            overwrite=arguments.overwrite,
            temporary_prefix="synastry-ledger",
            forbidden_identity=_source_identity(ledger),
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
