# Description tests and qualitative review

Read for trigger-description tuning, blind comparison, or interpretation beyond literal checks.

## Trigger set

Start with two realistic paraphrases of the intended request and one adjacent non-example. Expand to roughly 20 queries when useful: 8–10 positive cases and 8–10 difficult near-misses. Mix formal, casual, and implicit requests; include cases competing with neighboring skills. Avoid irrelevant negatives that merely inflate apparent success.

Store the intended routing in each case's `should_trigger` boolean and a `trigger` assertion. The boolean is an expected label, not an observation. The evaluator never decides whether a model actually selected a skill by reading the prompt or matching keywords. Record actual selection evidence manually with reviewer attribution; otherwise the assertion stays `not_run`.

Review the query set with the user. Reserve held-out queries before revising the description. Keep a description concise and discriminate against the closest adjacent task rather than merely making it more “pushy.” Compare candidates only on actually observed routing. Do not promise an automatic optimizer or invent a session model ID.

For this skill, the bundled two positive paraphrases ask to turn a recurring workflow into a skill and compare revisions; the adjacent negative asks to execute a task with an existing skill. These test the description's intended boundary, not measured trigger accuracy.

## Human artifact review

Show each prompt, baseline/candidate artifact, deterministic checks, and unresolved assertions. Ask what is wrong or better in specific terms. Use the user's requested delivery channel; no separate review server is required.

For visual checks, ask the reviewer to inspect the actual rendered artifact, not only generated code. Record reviewer, pass/fail judgment, and concrete evidence (for example, a saved screenshot path and observed clipping). The evaluator records this as attributed manual evidence; it cannot verify whether the reviewer actually inspected it.

## Optional blind comparison

When an independent reviewer is available, hide version labels and randomize presentation order. Use identical prompts, inputs, and criteria; ask for a preference with reasons and counterexamples. Keep the mapping outside the review until judgment is recorded. Do not call a self-review blind or independent.

## Analyze the evidence

Inspect assertion-level transitions and coverage before aggregate rates:

- An assertion passing every baseline and candidate may be nondiscriminating.
- A changed prompt, input, or rubric invalidates an apparent matched comparison.
- A higher pass rate with fewer checked assertions may reflect missing evidence.
- Conflicting runs suggest instability; examine individual results before summarizing.
- An improvement in literal compliance is not proof of improved semantics, usability, or model quality.

Summarize repeats only from saved result files for the same suite and label. Report run count and sample standard deviation when at least two observed rates exist. Do not infer resource consumption from file sizes or check counts; latency, tokens, and credits require separately recorded actual measurements.
