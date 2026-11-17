# Contributing

## Before you start

Set up the project with the [README](../README.md#setup), then run the tests as described in [Run the tests](how-to/run-the-tests.md).

## Rules for code

- **Keep every source file under 500 lines.** `spec-ops health` warns at 400 lines and fails over 500. Split large files into focused modules. This rule is in force. See ADR-0002 in `docs/project/adrs/accepted/`.
- Test through public entry points (the HTTP API, public modules, domain models), not private internals.
- Use `uv run ...` for Python tools. Do not call bare `pip` or make your own virtual environment.
- The web UI uses pnpm, not npm.

The full list of invariants, with the Definition of Ready and Definition of Done, is in the [operating manual](operating-manual.md).

## Rules for documentation

Documentation follows the Diataxis framework:

1. **Tutorials** (`docs/tutorials/`): lessons for beginners.
2. **How-to guides** (`docs/how-to/`): one task each.
3. **Reference** (`docs/reference/`): facts about commands, settings and the API.
4. **Explanation** (`docs/explanation/`): why the code is built the way it is.

Keep docs in step with the code. When you add or change a command, setting or endpoint, update its page. Keep the README short and link to the tutorial for detail. Write plain sentences and use fenced code blocks for every command.

Pages under `docs/project/` are specifications and decisions. Do not edit them as part of normal documentation work.

To build the documentation site you need the separate `spec-ops` tool:

```bash
uv run spec-ops docs build
```
