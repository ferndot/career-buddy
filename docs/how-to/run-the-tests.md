# Run the tests

Use this to check that your setup works or that a change did not break anything. Finish the [README setup](../../README.md#setup) first.

## Backend

```bash
uv run pytest -q
```

The tests drive the HTTP API end to end, plus some pure domain tests and Hypothesis property tests. A full run takes about two minutes.

Expected result: all tests pass except the known failure below, and 3 are skipped:

- `tests/test_llm_live.py` (2 tests) calls a real model. It runs when `CAREER_BUDDY_LIVE_ANTHROPIC_KEY` or `CAREER_BUDDY_LIVE_GEMINI_KEY` is set. It only lists models.
- `tests/test_s3_minio_integration.py` needs a real S3 server. It runs when `CAREER_BUDDY_S3_ENDPOINT` and the other S3 variables are set. See [Store originals in S3](store-originals-in-s3.md).

PDF tests skip when Chromium is missing. Run `uv run career-buddy install-browser` to include them.

Known failure: `tests/test_split_skills.py::test_no_skill_is_empty_or_holds_a_top_level_separator` fails at the moment.

Run one file or one test:

```bash
uv run pytest -q tests/test_api.py
```

## Frontend

```bash
pnpm -C frontend test
```

This runs vitest with jsdom. Check types with:

```bash
pnpm -C frontend typecheck
```

## File length check

Source files must stay under 500 lines. The [SpecOps](https://github.com/sanmak/specops) tool `spec-ops` checks it. It is a separate tool and `uv sync` does not install it. With it installed:

```bash
uv run spec-ops health
```

On Windows, set `PYTHONIOENCODING=utf-8` first if it fails with `UnicodeEncodeError` (PowerShell: `$env:PYTHONIOENCODING = "utf-8"`).
