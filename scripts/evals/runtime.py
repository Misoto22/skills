"""Reproducible run records, budget reservations, and iteration gates."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def fingerprint(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def make_run_record(
    *,
    suite_fingerprint: str,
    scoring_fingerprint: str,
    skill_fingerprint: str,
    candidate: dict[str, str],
    judge: dict[str, str],
) -> dict[str, Any]:
    """Build metadata without accepting credentials or arbitrary environment data."""

    safe_keys = {"provider", "model", "base_url_label"}

    def clean(item: dict[str, str]) -> dict[str, str]:
        return {key: item[key] for key in safe_keys if key in item}

    return {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "created_unix": int(time.time()),
        "fingerprints": {
            "suite": suite_fingerprint,
            "scoring": scoring_fingerprint,
            "skill": skill_fingerprint,
        },
        "models": {"candidate": clean(candidate), "judge": clean(judge)},
        "cases": [],
    }


@dataclass(frozen=True)
class CostReservation:
    calls: int
    cny: float

    @classmethod
    def from_plan(
        cls,
        *,
        cases: int,
        samples: int,
        retries: int,
        candidate_input_tokens: int,
        candidate_output_tokens: int,
        judge_input_tokens: int,
        judge_output_tokens: int,
        candidate_cny_per_million_input: float,
        candidate_cny_per_million_output: float,
        judge_cny_per_million_input: float,
        judge_cny_per_million_output: float,
        candidate_calls_per_sample: int = 1,
    ) -> CostReservation:
        counts = (cases, samples, retries, candidate_calls_per_sample)
        prices = (
            candidate_cny_per_million_input,
            candidate_cny_per_million_output,
            judge_cny_per_million_input,
            judge_cny_per_million_output,
        )
        if any(value < 0 for value in counts) or any(
            not math.isfinite(value) or value < 0 for value in prices
        ):
            raise ValueError("cost plan counts cannot be negative")
        attempts = retries + 1
        paired_calls = cases * samples * attempts
        candidate = (
            candidate_input_tokens * candidate_cny_per_million_input
            + candidate_output_tokens * candidate_cny_per_million_output
        ) / 1_000_000
        judge = (
            judge_input_tokens * judge_cny_per_million_input
            + judge_output_tokens * judge_cny_per_million_output
        ) / 1_000_000
        return cls(
            calls=paired_calls * (candidate_calls_per_sample + 1),
            cny=paired_calls * (candidate * candidate_calls_per_sample + judge),
        )


class BudgetLedger:
    """A process-shared, fail-closed CNY reservation ledger."""

    def __init__(self, path: Path, *, limit_cny: float) -> None:
        if not math.isfinite(limit_cny) or limit_cny <= 0:
            raise ValueError("budget limit must be positive CNY")
        self.path = path
        self.limit_cny = float(limit_cny)
        path.parent.mkdir(parents=True, exist_ok=True)

    def _locked(self):
        existed = self.path.exists()
        handle = self.path.open("a+", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        try:
            data = json.load(handle)
        except (json.JSONDecodeError, ValueError) as error:
            handle.seek(0, os.SEEK_END)
            if existed and handle.tell() > 0:
                handle.close()
                raise ValueError("budget ledger is corrupt; refusing to discard reservations") from error
            data = {"currency": "CNY", "limit_cny": self.limit_cny, "runs": {}}
        if data.get("currency") != "CNY" or float(data.get("limit_cny", -1)) != self.limit_cny:
            handle.close()
            raise ValueError("budget ledger currency or limit does not match this run")
        runs = data.get("runs")
        if not isinstance(runs, dict):
            handle.close()
            raise ValueError("budget ledger is corrupt; runs must be an object")
        for run_id, item in runs.items():
            if not isinstance(run_id, str) or not run_id or not isinstance(item, dict):
                handle.close()
                raise ValueError("budget ledger is corrupt; malformed run entry")
            reserved = item.get("reserved_cny")
            held = item.get("held_cny")
            if (
                not isinstance(reserved, (int, float))
                or isinstance(reserved, bool)
                or not math.isfinite(reserved)
                or reserved < 0
                or not isinstance(held, (int, float))
                or isinstance(held, bool)
                or not math.isfinite(held)
                or held < 0
                or (held > reserved and item.get("budget_breached") is not True)
            ):
                handle.close()
                raise ValueError("budget ledger is corrupt; invalid reservation values")
        return handle, data

    @staticmethod
    def _total(data: dict) -> float:
        return sum(float(item["held_cny"]) for item in data["runs"].values())

    def reserve(self, run_id: str, cny: float) -> None:
        if not run_id or not math.isfinite(cny) or cny < 0:
            raise ValueError("invalid budget reservation")
        handle, data = self._locked()
        try:
            if run_id in data["runs"]:
                raise ValueError("run already has a budget reservation")
            if self._total(data) + cny > self.limit_cny:
                raise ValueError("budget reservation exceeds the shared CNY limit")
            data["runs"][run_id] = {"reserved_cny": cny, "held_cny": cny, "usage_trusted": False}
            self._write(handle, data)
        finally:
            handle.close()

    def settle(self, run_id: str, *, actual_cny: float, usage_trusted: bool) -> None:
        handle, data = self._locked()
        try:
            item = data["runs"].get(run_id)
            if item is None:
                raise ValueError("run has no budget reservation")
            if not math.isfinite(actual_cny) or actual_cny < 0:
                raise ValueError("actual cost must be a finite nonnegative CNY amount")
            item["actual_cny"] = actual_cny
            item["usage_trusted"] = bool(usage_trusted)
            if usage_trusted:
                item["held_cny"] = actual_cny
            item["budget_breached"] = actual_cny > float(item["reserved_cny"])
            self._write(handle, data)
            if item["budget_breached"] or self._total(data) > self.limit_cny:
                raise ValueError("budget breached; actual cost exceeded its reservation")
        finally:
            handle.close()

    def snapshot(self) -> dict[str, Any]:
        handle, data = self._locked()
        try:
            return {**data, "reserved_cny": self._total(data)}
        finally:
            handle.close()

    @staticmethod
    def _write(handle, data: dict) -> None:
        handle.seek(0)
        handle.truncate()
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _rate(part: dict) -> float:
    return float(part["passed"]) / float(part["scored"]) if part["scored"] else 0.0


def _provenance_problem(provenance: object) -> str | None:
    if not isinstance(provenance, dict):
        return "provenance is missing"
    if not isinstance(provenance.get("head"), str) or not provenance["head"]:
        return "provenance head is missing"
    if not isinstance(provenance.get("dirty"), bool):
        return "provenance dirty flag is malformed"
    if not isinstance(provenance.get("dirty_fingerprint"), str) or not provenance["dirty_fingerprint"]:
        return "provenance dirty fingerprint is missing"
    return None


def _gate_run_problem(run: object, label: str) -> str | None:
    if not isinstance(run, dict):
        return f"{label} run is not an object"
    if not isinstance(run.get("run_id"), str) or not run["run_id"]:
        return f"{label} run has no run_id"
    provenance_problem = _provenance_problem(run.get("provenance"))
    if provenance_problem:
        return f"{label} run {provenance_problem}"
    fingerprints = run.get("fingerprints")
    if not isinstance(fingerprints, dict) or any(
        not isinstance(fingerprints.get(key), str) or not fingerprints[key]
        for key in ("suite", "scoring", "skill")
    ):
        return f"{label} run has malformed fingerprints"
    resolved = run.get("resolved_models")
    if not isinstance(resolved, dict):
        return f"{label} run has no resolved model identities"
    for role in ("candidate", "judge"):
        models = resolved.get(role)
        if (
            not isinstance(models, list)
            or not models
            or any(not isinstance(model, str) or not model for model in models)
            or len(models) != len(set(models))
        ):
            return f"{label} run has malformed resolved {role} models"
    if run.get("model_identity_trusted") is not True:
        return f"{label} run has no trusted deployment identity"
    if not isinstance(run.get("model_identity_fingerprint"), str) or not run["model_identity_fingerprint"]:
        return f"{label} run has no deployment identity fingerprint"
    independence = run.get("judge_independence")
    if (
        not isinstance(independence, dict)
        or independence.get("configured_separately") is not True
        or not isinstance(independence.get("resolved_distinct"), bool)
    ):
        return f"{label} run does not report judge configuration"
    if run.get("usage_trusted") is not True:
        return f"{label} run does not have trusted usage"
    actual = run.get("actual_cost")
    if (
        not isinstance(actual, dict)
        or actual.get("currency") != "CNY"
        or actual.get("trusted") is not True
        or isinstance(actual.get("amount"), bool)
        or not isinstance(actual.get("amount"), (int, float))
        or not math.isfinite(actual["amount"])
        or actual["amount"] < 0
    ):
        return f"{label} run has no trusted actual cost"
    summary = run.get("summary")
    if not isinstance(summary, dict) or not isinstance(summary.get("with"), dict):
        return f"{label} run has no with-skill arm"
    for split in ("tuning", "holdout"):
        part = summary["with"].get(split)
        if not isinstance(part, dict):
            return f"{label} run has no {split} summary"
        values = [part.get(key) for key in ("passed", "scored", "void")]
        if any(type(value) is not int or value < 0 for value in values):
            return f"{label} run has malformed {split} counts"
        if part["passed"] > part["scored"]:
            return f"{label} run has impossible {split} counts"
    cases = run.get("cases")
    if not isinstance(cases, list):
        return f"{label} run has no case results"
    if any(not isinstance(item, dict) for item in cases):
        return f"{label} run contains a non-object case result"
    selected = [item for item in cases if item.get("arm") == "with"]
    identities = []
    for item in selected:
        if (
            not isinstance(item.get("id"), str)
            or not item["id"]
            or type(item.get("sample")) is not int
            or item["sample"] < 1
            or item.get("split") not in {"tuning", "holdout"}
            or item.get("status") not in {"pass", "fail", "void"}
        ):
            return f"{label} run has a malformed case result"
        criteria = item.get("criteria")
        mechanical = item.get("mechanical")
        if (
            not isinstance(criteria, list)
            or not criteria
            or any(
                not isinstance(entry, dict) or not isinstance(entry.get("passed"), bool) for entry in criteria
            )
            or not isinstance(mechanical, list)
            or any(not isinstance(failure, str) for failure in mechanical)
        ):
            return f"{label} run has malformed scoring evidence"
        derived = "pass" if not mechanical and all(entry["passed"] for entry in criteria) else "fail"
        if item["status"] != derived:
            return f"{label} run status does not match scoring evidence"
        identities.append((item["id"], item["sample"], item["split"]))
    if len(identities) != len(set(identities)):
        return f"{label} run repeats a case sample"
    for split in ("tuning", "holdout"):
        split_cases = [item for item in selected if item["split"] == split]
        expected = {
            "passed": sum(item["status"] == "pass" for item in split_cases),
            "scored": sum(item["status"] in {"pass", "fail"} for item in split_cases),
            "void": sum(item["status"] == "void" for item in split_cases),
        }
        if summary["with"][split] != expected:
            return f"{label} run {split} summary does not match its cases"
    return None


def compare_runs(before: dict, after: dict, *, minimum_tuning_gain: float = 0.0) -> dict[str, Any]:
    """Compare skill versions while requiring identical eval and scoring inputs."""

    if not math.isfinite(minimum_tuning_gain) or minimum_tuning_gain < 0:
        return {"status": "inconclusive", "reason": "minimum tuning gain is invalid"}
    for label, run in (("before", before), ("after", after)):
        problem = _gate_run_problem(run, label)
        if problem:
            return {"status": "inconclusive", "reason": problem}
    if before["run_id"] == after["run_id"]:
        return {"status": "inconclusive", "reason": "before and after name the same run"}
    for key in ("suite", "scoring"):
        if before["fingerprints"].get(key) != after["fingerprints"].get(key):
            return {"status": "inconclusive", "reason": f"{key} fingerprint changed"}
    if before["resolved_models"] != after["resolved_models"]:
        return {"status": "inconclusive", "reason": "resolved model identities changed"}
    if before["model_identity_fingerprint"] != after["model_identity_fingerprint"]:
        return {"status": "inconclusive", "reason": "deployment identity changed"}
    if before["fingerprints"]["skill"] == after["fingerprints"]["skill"]:
        return {"status": "inconclusive", "reason": "skill instruction fingerprint did not change"}
    before_summary = before["summary"]["with"]
    after_summary = after["summary"]["with"]
    before_cases = {
        (item["id"], item["sample"], item["split"]) for item in before["cases"] if item.get("arm") == "with"
    }
    after_cases = {
        (item["id"], item["sample"], item["split"]) for item in after["cases"] if item.get("arm") == "with"
    }
    if before_cases != after_cases:
        return {"status": "inconclusive", "reason": "case sample sets differ"}
    for split in ("tuning", "holdout"):
        left, right = before_summary[split], after_summary[split]
        if left.get("void") or right.get("void"):
            return {"status": "inconclusive", "reason": f"{split} contains void samples"}
        if left.get("scored") != right.get("scored") or not left.get("scored"):
            return {"status": "inconclusive", "reason": f"{split} sample counts differ or are empty"}
    tuning_gain = _rate(after_summary["tuning"]) - _rate(before_summary["tuning"])
    holdout_gain = _rate(after_summary["holdout"]) - _rate(before_summary["holdout"])
    passed = tuning_gain > minimum_tuning_gain and holdout_gain >= 0
    return {
        "status": "pass" if passed else "fail",
        "tuning_gain": tuning_gain,
        "holdout_gain": holdout_gain,
        "skill_changed": True,
    }


def combine_iteration_phases(tuning: dict, holdout: dict, *, label: str) -> dict[str, Any]:
    """Combine two independently paid split runs for one instruction version."""

    for split, run in (("tuning", tuning), ("holdout", holdout)):
        if not isinstance(run, dict):
            raise ValueError(f"{label} {split} run is not an object")
        config = run.get("run_config")
        if not isinstance(config, dict) or config.get("split") != split:
            raise ValueError(f"{label} {split} run does not declare its split")
        if any(isinstance(item, dict) and item.get("split") != split for item in run.get("cases", [])):
            raise ValueError(f"{label} {split} run contains another split")
        provenance_problem = _provenance_problem(run.get("provenance"))
        if provenance_problem:
            raise ValueError(f"{label} {split} run {provenance_problem}")
    run_ids = [tuning.get("run_id"), holdout.get("run_id")]
    if any(not isinstance(run_id, str) or not run_id for run_id in run_ids):
        raise ValueError(f"{label} split run has no run_id")
    if run_ids[0] == run_ids[1]:
        raise ValueError(f"{label} reuses one run for both splits")
    if tuning["provenance"] != holdout["provenance"]:
        raise ValueError(f"{label} provenance differs across split runs")
    for key in ("suite", "scoring", "skill"):
        if tuning.get("fingerprints", {}).get(key) != holdout.get("fingerprints", {}).get(key):
            raise ValueError(f"{label} {key} fingerprint differs across split runs")
    if tuning.get("resolved_models") != holdout.get("resolved_models"):
        raise ValueError(f"{label} resolved models differ across split runs")
    if tuning.get("model_identity_fingerprint") != holdout.get("model_identity_fingerprint"):
        raise ValueError(f"{label} deployment identity differs across split runs")
    cases = [*tuning.get("cases", []), *holdout.get("cases", [])]
    combined = {
        "run_id": f"{tuning.get('run_id')}+{holdout.get('run_id')}",
        "fingerprints": dict(tuning["fingerprints"]),
        "provenance": dict(tuning["provenance"]),
        "resolved_models": tuning.get("resolved_models"),
        "model_identity_trusted": (
            tuning.get("model_identity_trusted") is True and holdout.get("model_identity_trusted") is True
        ),
        "model_identity_fingerprint": tuning.get("model_identity_fingerprint"),
        "judge_independence": {
            "configured_separately": (
                tuning.get("judge_independence", {}).get("configured_separately") is True
                and holdout.get("judge_independence", {}).get("configured_separately") is True
            ),
            "resolved_distinct": (
                tuning.get("judge_independence", {}).get("resolved_distinct") is True
                and holdout.get("judge_independence", {}).get("resolved_distinct") is True
            ),
        },
        "usage_trusted": tuning.get("usage_trusted") is True and holdout.get("usage_trusted") is True,
        "actual_cost": {
            "currency": "CNY",
            "trusted": (
                tuning.get("actual_cost", {}).get("trusted") is True
                and holdout.get("actual_cost", {}).get("trusted") is True
            ),
            "amount": sum(run.get("actual_cost", {}).get("amount", math.nan) for run in (tuning, holdout)),
        },
        "cases": cases,
    }
    with_cases = [item for item in cases if isinstance(item, dict) and item.get("arm") == "with"]
    combined["summary"] = {
        "with": {
            split: {
                "passed": sum(
                    item.get("status") == "pass" for item in with_cases if item.get("split") == split
                ),
                "scored": sum(
                    item.get("status") in {"pass", "fail"}
                    for item in with_cases
                    if item.get("split") == split
                ),
                "void": sum(
                    item.get("status") == "void" for item in with_cases if item.get("split") == split
                ),
            }
            for split in ("tuning", "holdout")
        }
    }
    return combined


def compare_iteration_runs(
    before_tuning: dict,
    before_holdout: dict,
    after_tuning: dict,
    after_holdout: dict,
    *,
    minimum_tuning_gain: float = 0.0,
) -> dict[str, Any]:
    """Gate a four-phase instruction-bundle iteration."""

    try:
        before = combine_iteration_phases(before_tuning, before_holdout, label="before")
        after = combine_iteration_phases(after_tuning, after_holdout, label="after")
    except (KeyError, TypeError, ValueError) as error:
        return {"status": "inconclusive", "reason": str(error)}
    return compare_runs(before, after, minimum_tuning_gain=minimum_tuning_gain)
