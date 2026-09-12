"""Exercise the native import boundary with a real JSON-RPC child process."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/dev/skills/handoff/scripts"


def load_native():
    spec = importlib.util.spec_from_file_location("handoff_native", SCRIPTS / "native.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SERVER = r"""
import json, sys, time
from pathlib import Path
home = Path(sys.argv[1])
mode = sys.argv[2]
source = str(home / "source.jsonl")
target = str(home / "rollout.jsonl")
for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if "id" not in request:
        continue
    result = {}
    if method == "initialize":
        result = {"codexHome": str(home if mode != "wrong_home" else home / "other")}
    elif method == "externalAgentConfig/detect":
        if mode == "slow_discovery":
            time.sleep(0.15)
        with (home / "detect-calls").open("a") as record:
            record.write("detect\n")
        sessions = [{"path": source, "cwd": str(home)}]
        result = {"items": [{"itemType": "SESSIONS", "details": {"sessions": sessions}}]}
    elif method == "externalAgentConfig/import":
        assert [i["itemType"] for i in request["params"]["migrationItems"]] == ["SESSIONS"]
        failure = {"subErrorType": "session_not_detected", "message": "private detail must not escape"}
        failures = [failure] if mode == "failed" else []
        successes = [] if mode in ("failed", "continued") else [{"target": "thread-1", "source": source}]
        outcome = {"itemType": "SESSIONS", "successes": successes, "failures": failures}
        notification = {"method": "externalAgentConfig/import/completed",
                        "params": {"importId": "import-1", "itemTypeResults": [outcome]}}
        print(json.dumps(notification), flush=True)
        result = {"importId": "import-1"}
    elif method == "thread/read":
        if mode == "unreadable":
            error = {"code": -1, "message": "private detail"}
            print(json.dumps({"id": request["id"], "error": error}), flush=True)
            continue
        result = {"thread": {"id": "thread-1", "path": target}}
    elif method == "thread/name/set":
        (home / "named.json").write_text(json.dumps(request["params"]))
    print(json.dumps({"id": request["id"], "result": result}), flush=True)
"""


class NativeImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.server = self.home / "server.py"
        self.server.write_text(SERVER)
        (self.home / "source.jsonl").write_text("{}\n")
        (self.home / "rollout.jsonl").write_text("{}\n")
        self.source = SimpleNamespace(
            path=self.home / "source.jsonl", cwd=str(self.home), title="Readable title", archived=False
        )
        self.native = load_native()

    def client(self, mode="ok"):
        return self.native.NativeCodex(
            self.home, command=[sys.executable, "-u", str(self.server), str(self.home), mode], timeout=3
        )

    def test_import_waits_for_completion_and_verifies_the_native_task(self):
        with self.client() as client:
            result = client.import_session(self.source)
        self.assertEqual(result.thread_id, "thread-1")
        self.assertEqual(result.rollout_path, self.home / "rollout.jsonl")
        self.assertTrue(result.changed)
        self.assertEqual(json.loads((self.home / "named.json").read_text())["name"], "Readable title")

    def test_large_history_discovery_has_its_own_timeout(self):
        with self.client("slow_discovery") as client:
            client.timeout = 0.05
            result = client.import_session(self.source)
            self.assertTrue(result.changed)
            self.assertEqual(client.timeout, 0.05)

    def test_an_unrecognized_source_does_not_rescan_all_history_repeatedly(self):
        missing = SimpleNamespace(path=self.home / "unrecognized.jsonl", cwd=str(self.home), title="Other")
        missing.path.write_text("{}\n")
        with self.client("success") as client:
            for _ in range(2):
                with self.assertRaisesRegex(self.native.NativeError, "session_not_detected"):
                    client.import_session(missing)
        self.assertEqual((self.home / "detect-calls").read_text().splitlines(), ["detect"])

    def test_completion_failure_is_not_reported_as_success(self):
        with (
            self.client("failed") as client,
            self.assertRaisesRegex(self.native.NativeError, "session_not_detected") as error,
        ):
            client.import_session(self.source)
        self.assertNotIn("private detail", str(error.exception))

    def test_native_task_must_be_readable_even_after_success_notification(self):
        with self.client("unreadable") as client, self.assertRaises(self.native.NativeError):
            client.import_session(self.source)

    def test_native_preserved_continuation_is_returned_as_unchanged(self):
        (self.home / "external_agent_session_imports.json").write_text(
            json.dumps(
                {"records": [{"source_path": str(self.source.path), "imported_thread_id": "thread-1"}]}
            )
        )
        with self.client("continued") as client:
            result = client.import_session(self.source)
        self.assertFalse(result.changed)
        self.assertFalse((self.home / "named.json").exists())

    def test_empty_success_without_an_existing_import_is_a_failure(self):
        with (
            self.client("continued") as client,
            self.assertRaisesRegex(self.native.NativeError, "no_import_result"),
        ):
            client.import_session(self.source)

    def test_wrong_native_home_is_rejected_before_import(self):
        with self.assertRaisesRegex(self.native.NativeError, "home_mismatch"), self.client("wrong_home"):
            pass


if __name__ == "__main__":
    unittest.main()
