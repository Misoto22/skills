"""Restricted tools for model-driven evaluation inside copied fixtures."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def _macos_path_aliases(path: Path) -> set[str]:
    aliases = {str(path), str(path.resolve())}
    for raw in list(aliases):
        if raw.startswith("/var/"):
            aliases.add("/private" + raw)
        elif raw.startswith("/private/var/"):
            aliases.add(raw.removeprefix("/private"))
    return aliases


def _redact_sandbox_paths(text: str, root: Path, temporary: Path) -> str:
    replacements = {
        **{raw: "." for raw in _macos_path_aliases(root)},
        **{raw: "<sandbox>" for raw in _macos_path_aliases(temporary)},
    }
    for raw, safe in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(raw, safe)
    return text


class ToolSandbox:
    MAX_FILE_BYTES = 1_000_000

    def __init__(
        self,
        fixture_root: Path,
        commands: dict[str, object],
        allowed_tools: set[str] | None = None,
    ) -> None:
        if not fixture_root.is_dir():
            raise ValueError("fixture root must be a directory")
        for path in fixture_root.rglob("*"):
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError("fixture tree must not contain symlinks")
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError("fixture tree must contain only regular files and directories")
            if stat.S_ISREG(mode) and path.stat().st_size > self.MAX_FILE_BYTES:
                raise ValueError("fixture file exceeds the evaluation size limit")
        self._temporary = tempfile.TemporaryDirectory(prefix="skill-eval-tool-")
        self.root = Path(self._temporary.name) / "workspace"
        shutil.copytree(fixture_root, self.root)
        self.home = Path(self._temporary.name) / "home"
        self.home.mkdir()
        self.commands = commands
        self.allowed_tools = allowed_tools or {"read_file", "write_file", "run_command"}

    def close(self) -> None:
        self._temporary.cleanup()

    def _path(self, raw: object) -> Path:
        if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
            raise ValueError("path must be relative to the sandbox")
        path = (self.root / raw).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("path escapes the sandbox")
        return path

    def definitions(self) -> list[dict]:
        definitions = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a UTF-8 file inside the evaluation workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write a UTF-8 file inside the evaluation workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run one command declared by the evaluation case. Available names: "
                    + ", ".join(sorted(self.commands)),
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string", "enum": sorted(self.commands)}},
                        "required": ["command"],
                        "additionalProperties": False,
                    },
                },
            },
        ]
        return [item for item in definitions if item["function"]["name"] in self.allowed_tools]

    def call(self, name: str, arguments: dict) -> str:
        if name not in self.allowed_tools:
            raise ValueError("tool is not allowed by this evaluation case")
        if name == "read_file":
            path = self._path(arguments.get("path"))
            if path.stat().st_size > self.MAX_FILE_BYTES:
                raise ValueError("file exceeds the evaluation size limit")
            return path.read_text(encoding="utf-8")
        if name == "write_file":
            path = self._path(arguments.get("path"))
            content = arguments.get("content")
            if not isinstance(content, str):
                raise ValueError("content must be a string")
            if len(content.encode("utf-8")) > self.MAX_FILE_BYTES:
                raise ValueError("content exceeds the evaluation size limit")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return json.dumps({"written": str(path.relative_to(self.root))})
        if name != "run_command":
            raise ValueError("tool is not allowed")
        command = arguments.get("command")
        if command not in self.commands:
            raise ValueError("command was not declared by the evaluation case")
        declaration = self.commands[command]
        argv = declaration.get("argv") if isinstance(declaration, dict) else declaration
        if not isinstance(argv, list) or not argv or any(not isinstance(item, str) for item in argv):
            raise ValueError("declared command is malformed")
        executable_path = Path(argv[0])
        allowed_executables = {Path(sys.executable).resolve()}
        if not executable_path.is_absolute() or executable_path.resolve() not in allowed_executables:
            raise ValueError("declared executable is outside the fixed allowlist")
        executable = str(executable_path.resolve())
        environment = {
            "HOME": str(self.home),
            "TMPDIR": str(Path(self._temporary.name) / "tmp"),
            "PATH": os.pathsep.join((str(Path(sys.executable).resolve().parent), "/usr/bin", "/bin")),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if isinstance(declaration, dict):
            for key, relative in declaration.get("env", {}).items():
                if not isinstance(key, str) or not key.isupper() or not isinstance(relative, str):
                    raise ValueError("declared environment is malformed")
                if any(marker in key for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")):
                    raise ValueError("declared environment may not contain credential variables")
                environment[key] = str(self._path(relative))
        Path(environment["TMPDIR"]).mkdir()
        result = subprocess.run(
            [executable, *argv[1:]],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        stdout = _redact_sandbox_paths(result.stdout, self.root, Path(self._temporary.name))
        stderr = _redact_sandbox_paths(result.stderr, self.root, Path(self._temporary.name))
        return json.dumps(
            {"exit_code": result.returncode, "stdout": stdout[-8000:], "stderr": stderr[-2000:]}
        )
