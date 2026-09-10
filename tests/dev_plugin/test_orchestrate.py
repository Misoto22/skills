"""The orchestrate hook, in-process for its decisions and through a process for its contract.

This guard is the only thing standing between an expensive model and the habit of doing
the work itself, so the tests that matter are the ones about what it still lets through:
a subagent, a write outside the project, a read-only command. A hook that refuses those
teaches the orchestrator to stop using the tool rather than to delegate the work.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "plugins" / "dev" / "hooks" / "orchestrate.py"

FABLE = "claude-fable-5-1"
GPT6 = "gpt-6-astra"
SONNET = "claude-sonnet-4-5"
# Codex marks a plugin hook process with the installed plugin root.
CODEX_CACHE = "/plugins/cache/misoto22/dev"
# One padding line covers well over a third of the tail window, so three of them put the
# window's start inside the first one rather than on a line boundary.
PADDING = json.dumps({"type": "user", "message": {"role": "user", "content": "x" * (200 * 1024)}})


def _load():
    spec = importlib.util.spec_from_file_location("orchestrate", HOOK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


orchestrate = _load()


@contextlib.contextmanager
def environment(**values: str):
    """Exactly these variables, because the machine running the tests is also a client."""
    with mock.patch.dict(os.environ, values, clear=True):
        yield


def run(event: dict, argv: str | None = None, **env: str) -> tuple[int, str]:
    """Drive main() over one event and return its exit code and stdout."""
    stdout = io.StringIO()
    with (
        environment(**env),
        mock.patch.object(orchestrate, "_run_ps", lambda pid: argv),
        mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))),
        contextlib.redirect_stdout(stdout),
    ):
        code = orchestrate.main()
    return code, stdout.getvalue()


def decision(output: str) -> dict:
    return json.loads(output)["hookSpecificOutput"]


class ModelSourceTests(unittest.TestCase):
    def transcript(self, directory: str, *lines: str) -> str:
        path = Path(directory) / "session.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def test_codex_names_the_model_on_the_event(self) -> None:
        self.assertEqual(orchestrate.model_from_event({"model": GPT6}), GPT6)

    def test_an_absent_or_empty_event_model_is_no_answer(self) -> None:
        for event in ({}, {"model": ""}, {"model": 7}):
            with self.subTest(event=event):
                self.assertIsNone(orchestrate.model_from_event(event))

    def test_the_last_assistant_line_of_a_transcript_wins(self) -> None:
        """A `/model` switch mid-session leaves the earlier lines naming the old model."""
        with tempfile.TemporaryDirectory() as temporary:
            transcript = Path(temporary) / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "user", "message": {"role": "user"}}),
                        json.dumps({"type": "assistant", "message": {"model": SONNET}}),
                        json.dumps({"type": "assistant", "message": {"model": FABLE}}),
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(orchestrate.model_from_transcript(str(transcript)), FABLE)

    def test_a_transcript_that_cannot_be_read_is_no_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            junk = Path(temporary) / "junk.jsonl"
            junk.write_bytes(b'\xff\xfe not json at all\n{"half": ')
            for path in (None, "", 7, str(Path(temporary) / "absent.jsonl"), str(junk)):
                with self.subTest(path=path):
                    self.assertIsNone(orchestrate.model_from_transcript(path))

    def test_a_transcript_line_without_an_assistant_model_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            transcript = Path(temporary) / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "user", "message": {"model": SONNET}}),
                        json.dumps({"type": "assistant", "message": {"model": ""}}),
                        json.dumps({"type": "assistant"}),
                        json.dumps([1, 2, 3]),
                        json.dumps({"model": FABLE}),
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(orchestrate.model_from_transcript(str(transcript)), FABLE)

    def test_a_subagent_turn_in_the_transcript_is_not_the_session_s_model(self) -> None:
        """A sidechain runs on the cheap model on purpose; reading it would answer with it."""
        with tempfile.TemporaryDirectory() as temporary:
            transcript = Path(temporary) / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "assistant", "message": {"model": FABLE}}),
                        json.dumps({"type": "assistant", "isSidechain": True, "message": {"model": SONNET}}),
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(orchestrate.model_from_transcript(str(transcript)), FABLE)

    def test_a_model_named_inside_a_record_is_not_that_record_s_model(self) -> None:
        """A dispatch names the model it delegates to, and a user turn can quote any model."""
        assistant = {
            "type": "assistant",
            "uuid": "a1",
            "message": {
                "id": "msg_01",
                "role": "assistant",
                "model": FABLE,
                "content": [
                    {"type": "text", "text": "Dispatching the edit."},
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "Agent",
                        "input": {"model": SONNET, "subagent_type": "dev:implementer"},
                    },
                ],
            },
        }
        quoted = f'the transcript reads {{"model":"{FABLE}"}} and then {{"model":"{SONNET}"}}'
        user = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": quoted}]}}
        with tempfile.TemporaryDirectory() as temporary:
            path = self.transcript(temporary, json.dumps(assistant), json.dumps(user))

            self.assertEqual(orchestrate.model_from_transcript(path), FABLE)

    def test_a_line_break_character_inside_a_json_string_does_not_split_the_record(self) -> None:
        """U+0085, U+2028 and U+2029 are legal in a JSON string and are line breaks to Python."""
        pasted = "next\x85line\u2028paragraph\u2029separator"
        record = json.dumps(
            {"type": "assistant", "message": {"content": pasted, "model": FABLE}}, ensure_ascii=False
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = self.transcript(temporary, record)

            self.assertGreater(len(record.splitlines()), 1, "the fixture must hold a literal break")
            self.assertEqual(orchestrate.model_from_transcript(path), FABLE)

    def test_a_tail_read_landing_mid_line_skips_the_leading_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.transcript(
                temporary,
                PADDING,
                PADDING,
                PADDING,
                json.dumps({"type": "assistant", "message": {"model": SONNET}}),
                json.dumps({"type": "assistant", "message": {"model": FABLE}}),
            )
            size = Path(path).stat().st_size
            with open(path, "rb") as handle:
                handle.seek(size - orchestrate.TRANSCRIPT_TAIL_BYTES - 1)
                cut = handle.read(1)

            self.assertGreater(size, orchestrate.TRANSCRIPT_TAIL_BYTES)
            self.assertNotEqual(cut, b"\n", "the fixture must cut a line in half")
            self.assertEqual(orchestrate.model_from_transcript(path), FABLE)

    def test_an_assistant_line_before_the_tail_window_is_out_of_reach(self) -> None:
        """The accepted trade for not reading tens of megabytes: the argv still answers here."""
        with tempfile.TemporaryDirectory() as temporary:
            path = self.transcript(
                temporary,
                json.dumps({"type": "assistant", "message": {"model": FABLE}}),
                PADDING,
                PADDING,
                PADDING,
            )

            self.assertGreater(Path(path).stat().st_size, orchestrate.TRANSCRIPT_TAIL_BYTES)
            self.assertIsNone(orchestrate.model_from_transcript(path))

    def test_the_launch_argv_carries_the_model_in_either_spelling(self) -> None:
        for argv in (f"node claude --model {FABLE} --verbose", f"node claude --model={FABLE}"):
            with (
                self.subTest(argv=argv),
                environment(CLAUDE_PID="4242"),
                mock.patch.object(orchestrate, "_run_ps", lambda pid, found=argv: found),
            ):
                self.assertEqual(orchestrate.model_from_argv(), FABLE)

    def test_an_unreadable_or_modelless_argv_is_no_answer(self) -> None:
        for argv in (None, "", "node claude --verbose"):
            with (
                self.subTest(argv=argv),
                environment(CLAUDE_PID="not-a-pid"),
                mock.patch.object(orchestrate, "_run_ps", lambda pid, found=argv: found),
            ):
                self.assertIsNone(orchestrate.model_from_argv())

    def test_the_process_reader_survives_a_missing_ps(self) -> None:
        with mock.patch.object(orchestrate.subprocess, "run", side_effect=OSError("no ps")):
            self.assertIsNone(orchestrate._run_ps("1"))

    def test_the_process_reader_ignores_a_ps_that_found_no_process(self) -> None:
        """Mocked rather than run against a real pid: `ps` differs between macOS and Linux."""
        gone = subprocess.CompletedProcess(["ps"], 1, stdout="", stderr="no such process")
        with mock.patch.object(orchestrate.subprocess, "run", return_value=gone):
            self.assertIsNone(orchestrate._run_ps("0"))

    def test_the_process_reader_hands_ps_no_stdin(self) -> None:
        """The hook's own stdin carries the event; a child inheriting it could consume it."""
        found = subprocess.CompletedProcess(["ps"], 0, stdout=f"claude --model {FABLE}", stderr="")
        with mock.patch.object(orchestrate.subprocess, "run", return_value=found) as reader:
            self.assertEqual(orchestrate._run_ps("4242"), f"claude --model {FABLE}")

        self.assertEqual(reader.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_the_transcript_outranks_the_stale_argv(self) -> None:
        """After a `/model` switch the argv still names the launch model; the transcript is current."""
        with tempfile.TemporaryDirectory() as temporary:
            transcript = Path(temporary) / "session.jsonl"
            transcript.write_text(json.dumps({"type": "assistant", "message": {"model": SONNET}}), "utf-8")
            event = {"transcript_path": str(transcript)}
            with (
                environment(),
                mock.patch.object(orchestrate, "_run_ps", lambda pid: f"claude --model {FABLE}"),
            ):
                self.assertEqual(orchestrate.resolve_model(event), SONNET)

    def test_the_event_outranks_everything(self) -> None:
        with environment(), mock.patch.object(orchestrate, "_run_ps", lambda pid: f"claude --model {FABLE}"):
            self.assertEqual(orchestrate.resolve_model({"model": GPT6}), GPT6)

    def test_argv_answers_when_the_transcript_is_still_empty(self) -> None:
        with environment(), mock.patch.object(orchestrate, "_run_ps", lambda pid: f"claude --model {FABLE}"):
            self.assertEqual(orchestrate.resolve_model({"transcript_path": "/nowhere.jsonl"}), FABLE)


class OrchestratorListTests(unittest.TestCase):
    def test_the_default_covers_both_orchestrator_families(self) -> None:
        with environment():
            self.assertEqual(orchestrate.orchestrator_models(), ["fable", "gpt-6"])

    def test_the_bare_variable_wins_over_the_plugin_option(self) -> None:
        with environment(ORCHESTRATOR_MODELS="opus", CLAUDE_PLUGIN_OPTION_ORCHESTRATOR_MODELS="fable"):
            self.assertEqual(orchestrate.orchestrator_models(), ["opus"])

    def test_the_plugin_option_applies_when_nothing_was_set_by_hand(self) -> None:
        with environment(CLAUDE_PLUGIN_OPTION_ORCHESTRATOR_MODELS="Fable, GPT-6 , "):
            self.assertEqual(orchestrate.orchestrator_models(), ["fable", "gpt-6"])

    def test_an_empty_value_is_an_off_switch_rather_than_a_fall_through(self) -> None:
        for values in ({"ORCHESTRATOR_MODELS": ""}, {"ORCHESTRATOR_MODELS": "  ,  "}):
            with self.subTest(values=values), environment(**values):
                self.assertEqual(orchestrate.orchestrator_models(), [])

    def test_a_model_is_matched_case_insensitively_on_a_substring(self) -> None:
        with environment():
            self.assertTrue(orchestrate.is_orchestrator(FABLE))
            self.assertTrue(orchestrate.is_orchestrator("CLAUDE-FABLE-5-1"))
            self.assertTrue(orchestrate.is_orchestrator(GPT6))
            self.assertFalse(orchestrate.is_orchestrator(SONNET))
            self.assertFalse(orchestrate.is_orchestrator("gpt-5.6-luna"))

    def test_nothing_is_an_orchestrator_when_the_model_is_unknown(self) -> None:
        with environment():
            for model in (None, "", 7):
                with self.subTest(model=model):
                    self.assertFalse(orchestrate.is_orchestrator(model))

    def test_an_empty_list_disables_every_event(self) -> None:
        edit = {"hook_event_name": "PreToolUse", "tool_name": "Write", "model": GPT6, "cwd": "/x"}
        edit["tool_input"] = {"file_path": "/x/y.py"}
        for event in ({"hook_event_name": "UserPromptSubmit", "model": GPT6}, edit):
            with self.subTest(event=event["hook_event_name"]):
                self.assertEqual(run(event, ORCHESTRATOR_MODELS=""), (0, ""))


class PromptDirectiveTests(unittest.TestCase):
    def test_an_orchestrator_session_is_told_what_its_job_is(self) -> None:
        code, output = run(
            {"hook_event_name": "UserPromptSubmit", "prompt": "add a flag"}, argv=f"--model {FABLE}"
        )

        self.assertEqual(code, 0)
        self.assertIn(FABLE, output)
        self.assertIn("dev:implementer", output)
        self.assertIn("dev:verifier", output)
        self.assertIn("ORCHESTRATOR_MODELS", output)

    def test_a_cheap_session_hears_nothing(self) -> None:
        event = {"hook_event_name": "UserPromptSubmit", "prompt": "add a flag", "model": SONNET}

        self.assertEqual(run(event), (0, ""))

    def test_codex_is_told_to_spawn_an_agent_rather_than_to_name_a_claude_one(self) -> None:
        event = {"turn_id": "turn-1", "model": GPT6}
        code, output = run(event, PLUGIN_ROOT=CODEX_CACHE)

        self.assertEqual(code, 0)
        self.assertIn("agents.default_subagent_model", output)
        self.assertNotIn("dev:implementer", output)

    def test_claude_code_is_recognised_by_its_own_marker(self) -> None:
        event = {"turn_id": "turn-1", "model": FABLE}
        _, output = run(event, CLAUDECODE="1", PLUGIN_ROOT=CODEX_CACHE)

        self.assertIn("dev:implementer", output)


class SubagentTests(unittest.TestCase):
    def test_a_subagent_may_write_whatever_it_was_dispatched_to_write(self) -> None:
        """The subagent runs on the cheap model this hook exists to route work to."""
        with tempfile.TemporaryDirectory() as project:
            event = {
                "hook_event_name": "PreToolUse",
                "agent_id": "agent_01",
                "agent_type": "dev:implementer",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(Path(project) / "src" / "x.py")},
                "cwd": project,
                "model": GPT6,
            }

            self.assertEqual(run(event), (0, ""))

    def test_a_subagent_is_not_told_to_delegate_further(self) -> None:
        event = {"hook_event_name": "UserPromptSubmit", "agent_id": "agent_01", "model": GPT6}

        self.assertEqual(run(event), (0, ""))


class EditRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = self.temporary.name
        self.addCleanup(self.temporary.cleanup)

    def edit(self, tool: str, tool_input: dict, **extra: object) -> tuple[int, str]:
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": tool,
            "tool_input": tool_input,
            "cwd": self.project,
            "model": GPT6,
        }
        event.update(extra)
        return run(event)

    def test_a_project_edit_is_refused_in_the_shape_both_clients_accept(self) -> None:
        code, output = self.edit("Edit", {"file_path": str(Path(self.project) / "src" / "x.py")})

        self.assertEqual(code, 0)
        self.assertEqual(decision(output)["hookEventName"], "PreToolUse")
        self.assertEqual(decision(output)["permissionDecision"], "deny")
        reason = decision(output)["permissionDecisionReason"]
        self.assertIn("Edit", reason)
        self.assertIn("src/x.py", reason)
        self.assertIn("dev:implementer", reason)
        self.assertIn("reviewer", reason)

    def test_a_relative_path_is_inside_the_project_by_construction(self) -> None:
        code, output = self.edit("Write", {"file_path": "src/new.py"})

        self.assertEqual(code, 0)
        self.assertEqual(decision(output)["permissionDecision"], "deny")

    def test_a_notebook_edit_names_its_file_differently(self) -> None:
        code, output = self.edit("NotebookEdit", {"notebook_path": "analysis.ipynb", "new_source": "1"})

        self.assertEqual(code, 0)
        self.assertIn("analysis.ipynb", decision(output)["permissionDecisionReason"])

    def test_a_write_outside_the_project_is_how_a_brief_gets_written(self) -> None:
        for path in ("/tmp/claude-501/session/scratchpad/brief.md", "~/.claude/memory/MEMORY.md"):
            with self.subTest(path=path):
                self.assertEqual(self.edit("Write", {"file_path": path}), (0, ""))

    def test_a_cheap_model_edits_its_own_project(self) -> None:
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/x.py"},
            "cwd": self.project,
            "model": SONNET,
        }

        self.assertEqual(run(event), (0, ""))

    def test_a_tool_call_carrying_no_path_is_not_a_project_write(self) -> None:
        for tool_input in ({}, {"file_path": ""}, {"file_path": 7}, "not-a-dict"):
            with self.subTest(tool_input=tool_input):
                self.assertEqual(self.edit("Edit", tool_input), (0, ""))

    def test_any_other_tool_passes_untouched(self) -> None:
        for tool in ("Read", "Grep", "Agent", "WebFetch"):
            with self.subTest(tool=tool):
                self.assertEqual(self.edit(tool, {"file_path": "src/x.py"}), (0, ""))

    def test_an_event_naming_neither_kind_is_ignored(self) -> None:
        self.assertEqual(run({"hook_event_name": "SessionStart", "model": GPT6}), (0, ""))
        self.assertEqual(run({"session_id": "s1", "model": GPT6}), (0, ""))

    def test_a_missing_cwd_falls_back_to_the_hook_s_own_directory(self) -> None:
        event = {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}, "model": GPT6}
        code, output = run(event)

        self.assertEqual(code, 0)
        self.assertEqual(decision(output)["permissionDecision"], "deny")


class BashDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = self.temporary.name
        self.addCleanup(self.temporary.cleanup)

    def target(self, command: str) -> str | None:
        return orchestrate.bash_target(command, self.project)

    def test_the_common_shell_forms_of_a_project_edit_are_caught(self) -> None:
        for command in (
            "sed -i 's/a/b/' src/x.py",
            "sed -i.bak 's/a/b/' src/x.py",
            "perl -pi -e 's/a/b/' src/x.py",
            "env FOO=1 sed -i 's/x/y/' notes.py",
            "cat > out.txt",
            "cat >out.txt",
            "printf 'x' >> README.md",
            "tee log.txt",
            "mv a b",
            "cp -r src dst",
            "rm -rf build",
            "mkdir -p src/new",
            "touch src/new.py",
            "ln -s a b",
            "git apply fix.patch",
            "pytest && sed -i 's/a/b/' src/x.py",
        ):
            with self.subTest(command=command):
                self.assertIsNotNone(self.target(command))

    def test_everything_an_orchestrator_still_needs_runs(self) -> None:
        for command in (
            "echo hi > /tmp/x",
            "pytest 2>&1 | tail -5",
            "python3 -m unittest discover -s tests > /dev/null",
            "ruff check . 2>&1",
            "git status",
            "git commit -m x",
            "git diff --stat",
            "rm -rf /tmp/scratch",
            "grep -rn 'sed -i' plugins/",
            "sed -n '1,20p' src/x.py",
            "cat src/x.py",
            'sed -i "s/a/b/ src/x.py',
            "git apply --stat",
            "",
            "   ",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.target(command))

    def test_a_command_that_is_not_a_string_writes_nothing(self) -> None:
        for command in (None, 7, {"command": "rm x"}):
            with self.subTest(command=command):
                self.assertIsNone(self.target(command))

    def test_only_the_destination_of_a_copy_or_link_is_written(self) -> None:
        """`cp a b` reads a and writes b; naming the source refuses copying a file out."""
        self.assertIsNone(self.target("cp plugins/dev/hooks/orchestrate.py /tmp/x/"))
        self.assertIsNone(self.target("cp notes.md /tmp/claude-501/session/scratchpad/"))
        self.assertIsNone(self.target("cp src/one-operand-names-no-destination"))
        self.assertEqual(self.target("cp /tmp/a src/b"), "src/b")
        self.assertEqual(self.target("install -m 644 a b"), "b")
        self.assertEqual(self.target("ln -s /tmp/a b"), "b")

    def test_the_source_a_move_removes_counts_as_a_project_write(self) -> None:
        self.assertEqual(self.target("mv src/a /tmp/b"), "src/a")

    def test_an_empty_operand_names_no_file(self) -> None:
        """BSD sed takes the backup suffix as a word of its own: `sed -i '' 's/a/b/' file`."""
        self.assertEqual(self.target("sed -i '' 's/a/b/' src/x.py"), "src/x.py")

    def test_only_the_flags_sed_and_perl_cluster_with_i_are_in_place(self) -> None:
        for command in (
            "perl -Mstrict -e 'print' src/x.py",
            "perl -MList::Util -e 'print' src/x.py",
            "sed --posix 's/a/b/' src/x.py",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.target(command))
        for command in ("sed --in-place 's/a/b/' src/x.py", "sed --in-place=.bak 's/a/b/' src/x.py"):
            with self.subTest(command=command):
                self.assertEqual(self.target(command), "src/x.py")

    def test_a_heredoc_body_is_data_rather_than_shell_source(self) -> None:
        """A quoted line beginning `> ` would otherwise segment into a redirect to `quoted`."""
        command = "gh pr create --body \"$(cat <<'EOF'\n> quoted line\nEOF\n)\""

        self.assertIsNone(self.target(command))

    def test_a_redirect_written_beside_the_heredoc_operator_still_counts(self) -> None:
        self.assertEqual(self.target("cat <<EOF > out.txt\nline\nEOF"), "out.txt")
        self.assertEqual(self.target("cat > out.txt <<EOF\n> not a redirect\nEOF"), "out.txt")

    def test_a_tab_indented_terminator_closes_a_dash_heredoc(self) -> None:
        self.assertIsNone(self.target("cat <<-'EOF' > /dev/null\n> quoted line\n\tEOF"))

    def test_an_unterminated_heredoc_swallows_the_rest_of_the_command(self) -> None:
        """Fail open: an unclosed body is dropped rather than read as shell source."""
        self.assertIsNone(self.target("cat <<EOF\n> quoted line"))

    def test_a_trailing_redirect_operator_names_nothing(self) -> None:
        self.assertIsNone(self.target("echo hi >"))

    def test_the_refusal_names_the_path_and_what_still_runs(self) -> None:
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "sed -i 's/a/b/' src/x.py"},
            "cwd": self.project,
            "model": GPT6,
        }
        code, output = run(event)
        reason = decision(output)["permissionDecisionReason"]

        self.assertEqual(code, 0)
        self.assertIn("Bash", reason)
        self.assertIn("src/x.py", reason)
        self.assertIn("Read-only commands", reason)

    def test_a_command_writing_nothing_in_the_project_is_never_read_for_a_model(self) -> None:
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "cwd": self.project,
            "model": GPT6,
        }

        self.assertEqual(run(event), (0, ""))


class PatchRefusalTests(unittest.TestCase):
    """Codex's only edit tool. It reports `apply_patch` with the patch body in `command`."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = self.temporary.name
        self.addCleanup(self.temporary.cleanup)

    def body(self, *headers: str) -> str:
        return "\n".join(["*** Begin Patch", *headers, "*** End Patch", ""])

    def patch(self, command: object) -> tuple[int, str]:
        event = {
            "hook_event_name": "PreToolUse",
            "turn_id": "turn-1",
            "tool_name": "apply_patch",
            "tool_input": {"command": command},
            "cwd": self.project,
            "model": GPT6,
        }
        return run(event)

    def test_every_header_that_names_a_project_file_is_refused(self) -> None:
        for header, path in (
            ("*** Update File: src/app.py", "src/app.py"),
            ("*** Add File: src/new.py", "src/new.py"),
            ("*** Delete File: src/old.py", "src/old.py"),
            ("*** Move to: src/renamed.py", "src/renamed.py"),
        ):
            with self.subTest(header=header):
                code, output = self.patch(self.body(header, "@@", "-a", "+b"))

                self.assertEqual(code, 0)
                self.assertEqual(decision(output)["permissionDecision"], "deny")
                reason = decision(output)["permissionDecisionReason"]
                self.assertIn("apply_patch", reason)
                self.assertIn(path, reason)

    def test_a_patch_outside_the_project_is_how_a_brief_gets_written(self) -> None:
        body = self.body("*** Add File: /tmp/claude-501/session/scratchpad/brief.md", "+notes")

        self.assertEqual(self.patch(body), (0, ""))

    def test_a_body_naming_no_file_is_not_a_project_write(self) -> None:
        for command in ("", self.body(), None, 7, {"command": "*** Update File: src/x.py"}):
            with self.subTest(command=command):
                self.assertEqual(self.patch(command), (0, ""))


class ProjectBoundaryTests(unittest.TestCase):
    def test_a_path_that_cannot_be_resolved_is_left_alone(self) -> None:
        self.assertFalse(orchestrate.inside_project("", "/tmp"))
        self.assertFalse(orchestrate.inside_project("x.py", "\x00"))


class HookProcessTests(unittest.TestCase):
    """The stdin/stdout/exit contract, run the way both clients run it."""

    def run_hook(self, payload: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": os.environ.get("PATH", ""), "ORCHESTRATOR_MODELS": "fable,gpt-6"},
        )

    def test_a_project_edit_on_an_orchestrator_exits_zero_with_the_deny_object(self) -> None:
        with tempfile.TemporaryDirectory() as project:
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/x.py"},
                "cwd": project,
                "model": GPT6,
            }
            result = self.run_hook(json.dumps(event))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(decision(result.stdout)["permissionDecision"], "deny")

    def test_anything_unparseable_lets_the_tool_call_run(self) -> None:
        for payload in ("", "not json", "[]", '{"tool_input": "x"}', "null"):
            with self.subTest(payload=payload):
                result = self.run_hook(payload)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
