---
name: skill-creator
description: "Create and improve skills through test design, saved-output evaluation, comparison, and iteration. Use for skill authoring, skill benchmarks, or trigger-description tuning; not for ordinary task execution using an existing skill. Delegate authoring, validation, packaging, and saving authority to built-in create-skill."
---
# Skill Creator

Use this as the evaluation specialist, not a second installation workflow.

## Authoring boundary

For any new skill or edit, use built-in `create-skill` as the authoring, validation, packaging, and save lead. Follow its workspace instructions; preserve an update's name, scope, metadata, and complete resource tree. Supply evaluation findings without duplicating its save procedure or creating reciprocal skill calls.

If the lead is unavailable, prepare evaluation findings or an unsaved candidate only and explain the blocked handoff. Never substitute a local archive for a confirmed save.

## Evaluation loop

1. **Capture intent.** Extract the task, trigger context, expected outputs, inputs, edge cases, and success criteria from the conversation before asking for missing details. Match the user's technical vocabulary. Respect a request to skip evaluations. For drafting/interview guidance, read `references/authoring-and-iteration.md`.
2. **Freeze the comparison.** Preserve the pristine original as the baseline for an update; use no skill for a new-skill baseline. Fix identical prompts, inputs, assertions, and run conditions before comparing. Start with 2–3 realistic cases, including two trigger paraphrases and an adjacent negative. When tuning descriptions or planning blind review, read `references/trigger-and-review.md`.
3. **Collect evidence.** Use actual available execution facilities or ask the user for saved outputs; do not assume an external model runner exists. Record version, prompt, inputs, run conditions, and output location per run. Keep baseline and candidate artifacts separate. A prompt in a JSON file is not an executed test. Sequential self-runs are sanity checks, not independent model-quality evidence.
4. **Check saved outputs.** Before constructing a suite, read `references/evaluation.md` and `references/cases.schema.json`. Copy/adapt `examples/cases.json`. Run `scripts/evaluate.py` only against saved evidence, using the commands in `README.md`. Its literal-string/file checks are deterministic; execution, prompt-only, trigger, and visual assertions remain `not_run` without attributed manual evidence.
5. **Review and compare.** Compare matched baseline/candidate results with the bundled script. Report pass/fail/not_run counts, coverage, and comparable checked results; missing evidence is never a pass. Review artifacts with the user directly rather than promising an unavailable viewer. Record concrete feedback; empty feedback alone is not approval. Use repeated-run summaries only for result files that actually exist. Do not invent latency, token, or credit metrics.
6. **Revise and hand back.** Generalize the failure, remove instructions that cause wasted work, and bundle repeated deterministic work when useful. Re-evaluate the complete candidate on fresh outputs plus held-out cases. Stop on user satisfaction or lack of meaningful progress; report limitations and hand the candidate/findings to `create-skill`.

Example: given saved baseline/candidate outputs for three identical prompts, return assertion transitions and unresolved checks—not a quality claim from fixture passes.

## Tooling health

After changing the evaluator, run `python -B -m unittest discover -s tests -v` from this directory; `tests/test_evaluate.py` covers its contract. Read `README.md` for synthetic examples and commands. The standard-library tooling does not execute prompts, call models, access the network, or run arbitrary commands.
