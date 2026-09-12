"""Gate one skill revision against comparable with-skill evaluation records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evals.runtime import compare_iteration_runs


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: run record must be an object")
    return value


def benchmark_markdown(
    result: dict[str, Any],
    phases: dict[str, Path],
    records: dict[str, dict[str, Any]],
) -> str:
    lines = [
        "# Evaluation iteration gate",
        "",
        f"- Result: **{result['status']}**",
    ]
    for label in ("before_tuning", "before_holdout", "after_tuning", "after_holdout"):
        record = records[label]
        display = label.replace("_", " ").title()
        provenance = record.get("provenance")
        provenance = provenance if isinstance(provenance, dict) else {}
        head = provenance.get("head", "not recorded")
        dirty = provenance.get("dirty", "not recorded")
        dirty_fingerprint = provenance.get("dirty_fingerprint", "not recorded")
        models = record.get("models", "not recorded")
        lines.append(f"- {display}: `{phases[label]}`")
        lines.append(f"- {display} HEAD: `{head}`")
        lines.append(f"- {display} dirty: `{dirty}`")
        lines.append(f"- {display} dirty fingerprint: `{dirty_fingerprint}`")
        lines.append(f"- {display} models: `{json.dumps(models, ensure_ascii=False, sort_keys=True)}`")
    if result.get("reason"):
        lines.append(f"- Reason: {result['reason']}")
    if "tuning_gain" in result:
        lines.append(f"- Tuning gain: {result['tuning_gain']:.6f}")
        lines.append(f"- Holdout gain: {result['holdout_gain']:.6f}")
    if "skill_changed" in result:
        lines.append(f"- Skill fingerprint changed: {str(result['skill_changed']).lower()}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-tuning", type=Path, required=True, help="baseline tuning run JSON")
    parser.add_argument("--before-holdout", type=Path, required=True, help="baseline holdout run JSON")
    parser.add_argument("--after-tuning", type=Path, required=True, help="candidate tuning run JSON")
    parser.add_argument("--after-holdout", type=Path, required=True, help="candidate holdout run JSON")
    parser.add_argument("--benchmark", type=Path, help="write a compact Markdown gate record")
    parser.add_argument(
        "--minimum-tuning-gain",
        type=float,
        default=0.0,
        help="strict minimum score gain required for tuning (default: 0)",
    )
    args = parser.parse_args()
    phases = {
        "before_tuning": args.before_tuning,
        "before_holdout": args.before_holdout,
        "after_tuning": args.after_tuning,
        "after_holdout": args.after_holdout,
    }
    try:
        records = {label: load(path) for label, path in phases.items()}
        result = compare_iteration_runs(
            records["before_tuning"],
            records["before_holdout"],
            records["after_tuning"],
            records["after_holdout"],
            minimum_tuning_gain=args.minimum_tuning_gain,
        )
    except ValueError as error:
        records = {label: {} for label in phases}
        result = {"status": "inconclusive", "reason": str(error)}
    if args.benchmark:
        args.benchmark.parent.mkdir(parents=True, exist_ok=True)
        args.benchmark.write_text(benchmark_markdown(result, phases, records), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return {"pass": 0, "fail": 1, "inconclusive": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
