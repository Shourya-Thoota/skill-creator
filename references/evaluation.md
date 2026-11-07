# Saved-output evaluator contract

Read before creating test cases or interpreting results. `cases.schema.json` is the portable JSON Schema; the script implements its constraints with Python's standard library, without requiring a schema package.

## Input

The suite has `schema_version: 1` and a nonempty `cases` array. Each case has unique `id`, nonempty `prompt`, and nonempty `assertions`; optional `should_trigger` records the intended routing. IDs use letters, digits, hyphens, or underscores, starting with a letter or digit. Assertion IDs are unique within a case.

All assertions contain `id` and `type`; optional `description` names the check:

| Type | Additional fields | Evaluation |
|---|---|---|
| `required_string` | `file`, `value`; optional `case_sensitive` (default true) | Literal substring must exist in UTF-8 text |
| `forbidden_string` | same | Literal substring must be absent |
| `required_file` | `file` | Regular file must exist |
| `forbidden_file` | `file` | No file/directory entry at that path may exist |
| `execution` | none | Attributed manual evidence only |
| `prompt_only` | none | Attributed manual evidence only |
| `human_visual` | none | Attributed manual evidence only |
| `trigger` | none; case must have `should_trigger` | Manual pass means observed selection agrees with the expected label |

Unknown fields, duplicate JSON keys, unsafe paths, empty values, invalid field types, and unsupported versions are rejected (exit 2). `file` is a relative POSIX path inside `<outputs>/<case-id>/`: no absolute paths, backslashes, drive separators, `.`/`..`, or empty segments. Symlinks in evidence paths are not followed. Output/evidence trees are assumed stable during a run.

## Evidence and statuses

Point `--outputs` at the saved output root. A missing case directory makes every assertion `not_run`, including absence checks. An existing case directory declares the supplied output set, even if empty; create it only after recording an actual attempt.

In an existing case directory:

- A missing required file is `fail`; an absent forbidden path is `pass`.
- A missing text file, directory in place of text, non-UTF-8 content, unreadable file, oversized text (>8 MiB), or symlink path is `not_run`. Extract text from binary artifacts using an appropriate format specialist first; record the extraction provenance.
- A required regular-file check verifies existence, not format integrity. An existing directory fails that check.
- Execution, prompt-only, trigger, and visual assertions remain `not_run` unless a valid manual record is supplied. A completed literal check is not execution evidence.

Optional `--manual` input:

```json
{
  "schema_version": 1,
  "records": [
    {
      "case_id": "create-workflow",
      "assertion_id": "actual-routing",
      "status": "pass",
      "reviewer": "user",
      "evidence": "Observed the skill selected in the recorded run; record: iteration-1/routing.txt"
    }
  ]
}
```

Records must address known manual-only assertions, be unique, and have nonblank reviewer/evidence. Unknown fields are rejected. Manual evidence is an attributed claim, not independently verified by the evaluator. Do not manufacture a reviewer or evidence record to increase coverage.

## Results

Each assertion records `id`, `type`, `status` (`pass`, `fail`, `not_run`), evidence, and evidence kind. Case and overall status are `fail` if any check fails, otherwise `not_run` if any check is unresolved, otherwise `pass`. Counts always retain all three statuses.

`checked = pass + fail`; `pass_rate = pass / checked`, or null if none checked. `coverage = checked / total`. Missing results never add to passes. Report coverage next to rates.

The script fingerprints the full suite with SHA-256 over canonical parsed JSON. A comparison requires the same fingerprint and exactly matching case/assertion IDs and types; it lists both statuses and only computes paired rate differences where both sides were checked. Different output text is expected; different case definitions are not comparable. Counts and independent rates are also included, but must not be interpreted as an improvement when coverage differs.

`summarize` requires identical suites, labels, and assertion shapes, and refuses the same result path twice. It reports actual file count, pooled counts, and mean/sample standard deviation of observed per-run rates. It cannot establish that separately saved files represent independent runs; retain run provenance. It emits no latency, token, or credit claims.

CLI exit 0 means evaluation completed, not that assertions passed. Exit 2 means invalid input or an I/O error. Results go to `--out` (parent directory must exist); omit it to print JSON. No prompt execution, subprocess, dynamic code evaluation, network, or external package is used.
