# What the project declares

Three commands are read from the project rather than imposed on it: what it tests with,
what it lints with, and how it moves its version. **First match wins** in every table.
Step 0 records what matched; steps 2 and 3a run it.

## Test command

| Marker                               | Command                                                                 |
|--------------------------------------|-------------------------------------------------------------------------|
| `scripts/test`, `justfile`, `Makefile` target `test` | run that target                                          |
| `package.json` `scripts.test`        | `<pm> test` — pm via lockfile (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lock` → bun, else npm) |
| `Cargo.toml`                         | `cargo test`                                                            |
| `pyproject.toml`                     | `uv run pytest` if `uv.lock`; else `pytest`; else `python -m unittest`  |
| `go.mod`                             | `go test ./...`                                                         |
| `*.csproj` / `*.sln`                 | `dotnet test`                                                           |
| `Gemfile`                            | `bundle exec rake test` if `Rakefile`, else `rspec`                     |
| `tests/` or `test/` holding `test_*.py`, none of the markers above | `pytest <dir>` when a `conftest.py`, `pytest.ini`, or a `[tool.pytest*]` section exists; else `python3 -m unittest discover -s <dir>` |
| none of the above                    | read the project's CI before concluding there is none — see below       |

**A repository with no marker is not a repository with no tests.** A packaging file is
the usual place a test command is declared, not the only one: a repository can carry
hundreds of tests under `tests/` and ship no `pyproject.toml` at all. Before reporting
"no test command", read what the project's own CI runs — that is the command its
maintainers actually trust:

```bash
grep -hiE '(pytest|unittest|jest|vitest|rspec|go test|cargo test|dotnet test|npm test|make test)' .github/workflows/*.yml 2>/dev/null
```

Take the command it names, dropping CI-only decoration — a `-v`, a coverage wrapper, a
matrix variable. Step 2 SKIPs only when this finds nothing either.

Never report a run that did not happen. When a command is found but cannot run here — an
interpreter version the tests refuse, a dependency that is not installed — name the
command and say why it did not run. That is a different report from "no test command",
and collapsing the two hides a test suite nobody executed.

## Lint command

A linter the project does not configure is not this skill's to impose.

| Marker                                        | Command                                       |
|-----------------------------------------------|-----------------------------------------------|
| `lint` target in `scripts/`, `justfile`, `Makefile` | run that target                          |
| `package.json` `scripts.lint`                 | `<pm> run lint` — pm resolved as for the test command |
| `ruff.toml`, `.ruff.toml`, or `[tool.ruff]` in `pyproject.toml` | `ruff check .` and `ruff format --check .` |
| `Cargo.toml`                                  | `cargo clippy`                                |
| `.golangci.yml` / `.golangci.yaml`            | `golangci-lint run`                           |
| `go.mod`, none of the above                   | `go vet ./...`                                |
| none of the above                             | step 2b SKIPs                                 |

## Version bumper

Some projects publish from a version string, not from the default branch: an installer
that compares versions skips a merge that left the string alone, and its log says
"already at the latest version" while saying nothing untrue.

| Marker                                              | Command                                       |
|-----------------------------------------------------|-----------------------------------------------|
| `bump-version.py` / `bump_version.py` in `scripts/` | run it with the resolved version              |
| `bump` or `version` target in `scripts/`, `justfile`, `Makefile` | run that target                  |
| `package.json` with a `version` field               | `<pm> version <resolved>` — pm resolved as for the test command |
| `Cargo.toml` `[package]` `version`                  | `cargo set-version <resolved>`, or report and stop when `cargo-edit` is absent |
| none of the above                                   | step 3a SKIPs — nothing here declares a version to move |
