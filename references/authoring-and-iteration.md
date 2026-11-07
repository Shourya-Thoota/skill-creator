# Interview, draft, and iteration

Read while capturing intent or revising instructions. Use built-in `create-skill` for format rules and the actual authoring/save workflow; this reference supplies evaluation-oriented process knowledge only.

## Capture the workflow

Extract demonstrated tools, step order, corrections, inputs, output formats, and remedies from the conversation. Establish:

1. What capability should the skill enable?
2. Which user phrases or contexts should select it, and which adjacent requests should not?
3. What should the output contain or look like?
4. Which success criteria are objectively checkable, and which need judgment?

Ask only for gaps that affect the draft. Research dependencies before promising them. Suggest objective tests for transformations, extraction, and fixed workflows; use human review for style or visual quality. Explain “assertion” as a concrete check when the user is unfamiliar with testing terms.

## Draft with evaluation in mind

Describe the capability and triggering context in the description. Prefer imperative instructions, concrete output examples, and clear read conditions for optional references. Keep reusable static resources separate. Do not import environment-specific commands just because an older workflow used them.

Keep the user-facing output contract explicit. For example, a commit-message skill might turn “Added authentication with JWT tokens” into `feat(auth): implement JWT-based authentication`; test both the required prefix and meaning preservation, but leave the latter to a reviewer unless you have a sound objective check.

## Improve without overfitting

- Generalize from failures across cases rather than embedding one user's incidental file name or sentence.
- Read available execution records as well as final artifacts. Remove instructions that repeatedly cause wasted steps.
- Explain reasons for fragile requirements instead of adding emphatic rules.
- Look for repeated helper code across runs. Bundle stable deterministic transformations rather than recreating them each time.
- Include held-out cases and realistic boundary cases before claiming broad improvement.

## Organize iterations

Use an evaluation workspace, not the installed source. A useful layout is:

```text
iteration-1/
  cases.json
  baseline/<case-id>/output.txt
  candidate/<case-id>/output.txt
  baseline-results.json
  candidate-results.json
  comparison.json
  feedback.json
```

Preserve prompt/input identity and baseline version between comparisons. Record run conditions and any sequential self-run contamination. Do not create a case output directory before there are saved outputs; the evaluator treats an existing directory as the supplied output set, even if empty.

Record feedback with case ID, assertion ID if applicable, comment, reviewer, and evidence location. Missing feedback is missing evidence, not user acceptance. After revision, collect fresh outputs into the next iteration, rerun the checks, and review the actual artifacts. Choose the original or previous candidate as baseline explicitly; do not silently change baselines.

Hand the complete candidate and evaluation limitations back to `create-skill` for its full-tree validation and packaging. This reference defines no separate save operation.
