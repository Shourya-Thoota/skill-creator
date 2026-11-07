# Skill Creator

An agent skill for creating and improving other skills through test design, saved-output evaluation, comparison, and iteration. It is the evaluation specialist: it turns saved baseline and candidate outputs into pass/fail/coverage evidence you can act on, with bundled tooling to run assertion suites and compare revisions.

**By [Vibhav Thoota](https://github.com/Shourya-Thoota) / [Pansophy LLC](https://github.com/Shourya-Thoota).**

## What it does

- **Test design.** Build a case suite from a skill's intent: trigger paraphrases, adjacent negatives, literal/file checks, and manual observations. `references/cases.schema.json` defines the case format.
- **Saved-output evaluation.** `scripts/evaluate.py` scores saved outputs against the suite — deterministic for literal-string and file checks, honest `not_run` for anything without attributed evidence.
- **Comparison and iteration.** Compare baseline vs candidate on mutually checked assertions, summarize repeated runs, and report coverage instead of a hollow pass rate. A prompt in a JSON file is never treated as an executed test.

The standard-library tooling executes no prompts, calls no models, touches no network, and runs no arbitrary commands.

## When to use it

Use for skill authoring, skill benchmarks, and trigger-description tuning — not for ordinary task execution with an existing skill.

## Install

This is an [Agent Skill](https://agentskills.io) (a `SKILL.md` package). Clone it into your agent's skills directory:

```bash
git clone https://github.com/Shourya-Thoota/skill-creator ~/.claude/skills/skill-creator
```

Works with any agent that supports the Agent Skills format. Python 3.9+ for the evaluation tooling; no third-party packages.

## License

[MIT](LICENSE) - Copyright (c) 2026 Pansophy LLC.

---

# Skill Creator evaluation tools

# Skill Creator evaluation tools

Run from this skill's directory with Python 3.9+; no third-party packages are needed. Read `references/evaluation.md` before building a suite. `references/cases.schema.json` defines test-case input.

## Synthetic smoke example

The example output files are hand-written fixtures, not real model runs. The suite includes two positive trigger paraphrases, one adjacent negative, literal/file checks, and unresolved manual checks.

```bash
python -B scripts/evaluate.py evaluate --cases examples/cases.json --outputs examples/baseline --label baseline --out examples/baseline-results.json
python -B scripts/evaluate.py evaluate --cases examples/cases.json --outputs examples/candidate --label candidate --out examples/candidate-results.json
python -B scripts/evaluate.py compare examples/baseline-results.json examples/candidate-results.json --out examples/comparison.json
python -B scripts/evaluate.py summarize examples/candidate-results.json --out examples/candidate-summary.json
python -B -m unittest discover -s tests -v
```

For real runs, replace the fixture roots with independently collected outputs, retaining the same suite. Save text as `<outputs>/<case-id>/output.txt` and other artifacts at the paths declared in assertions. Do not create empty case directories for unexecuted cases. Review artifact formats separately; a file existence check is not a format validator.

To add real manual observations:

```bash
python -B scripts/evaluate.py evaluate --cases iteration-1/cases.json --outputs iteration-1/candidate --label candidate --manual iteration-1/manual.json --out iteration-1/candidate-results.json
```

Use the manual-record shape in `references/evaluation.md`; absence leaves manual checks `not_run`. To summarize repeats, supply distinct existing result files for the same label and suite:

```bash
python -B scripts/evaluate.py summarize iteration-1/candidate-results.json iteration-2/candidate-results.json --out candidate-repeats.json
```

Example result shape (one resolved assertion and one missing):

```json
{
  "status": "not_run",
  "counts": {"pass": 1, "fail": 0, "not_run": 1, "total": 2, "checked": 1, "pass_rate": 1.0, "coverage": 0.5}
}
```

Full results also contain suite identity, case-level results, and assertion evidence. A high checked-only rate with unresolved checks is not full success. Comparisons use only mutually checked assertions for paired deltas. Repeated summaries describe the supplied files, not hypothetical runs or resource use.

## Boundaries

These tools check saved evidence; they do not execute prompts, select skills, invoke models, or test real model quality. Manual assertions require attributed observations. Built-in `create-skill` remains the authoring/validation/package/save authority; this package implements no save procedure.

## Candidate verification record — October 25, 2026

- Ran `agentskills validate` on the complete candidate directory: accepted.
- Ran all 32 tests in [the evaluator test suite](tests/test_evaluate.py): passed.
- Ran the four synthetic example commands above; [the saved comparison](examples/comparison.json) records baseline 3 pass / 3 fail / 6 not_run and candidate 6 pass / 0 fail / 6 not_run, both with 50% coverage.
- [The saved single-result summary](examples/candidate-summary.json) has run count 1 and null sample standard deviation; no repeated model runs or resource metrics were measured.
- Reviewed the description against [the two positive paraphrases and adjacent negative](examples/cases.json): intended scope matches; actual routing remains untested and all three trigger assertions remain `not_run`.

This record covers tooling and intended scope, not a claim of improved real-model performance. Re-run validation and tests after edits.
