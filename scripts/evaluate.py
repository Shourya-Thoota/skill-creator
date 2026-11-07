#!/usr/bin/env python3
"""Deterministic checks of saved outputs. Python standard library only."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys


STRING_TYPES = {"required_string", "forbidden_string"}
FILE_TYPES = {"required_file", "forbidden_file"}
MANUAL_TYPES = {"execution", "prompt_only", "human_visual", "trigger"}
TYPES = STRING_TYPES | FILE_TYPES | MANUAL_TYPES
STATUSES = {"pass", "fail", "not_run"}
MAX_TEXT_BYTES = 8 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), "Expected a JSON object")
    require(set(required) <= obj.keys(), "Missing fields: " + str(set(required) - obj.keys()))
    require(obj.keys() <= set(required) | set(optional), "Unexpected fields: " +
            str(obj.keys() - set(required) - set(optional)))


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value)


def valid_path(value):
    return (nonblank(value) and value == value.strip() and not value.startswith("/") and
            not any(c in value for c in "\\:") and
            not any(ord(c) < 32 for c in value) and
            all(p not in {"", ".", ".."} for p in value.split("/")))


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path):
    def invalid_constant(value):
        raise ValueError("Invalid JSON constant: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def validate_suite(suite):
    fields(suite, {"schema_version", "cases"})
    require(type(suite["schema_version"]) is int and suite["schema_version"] == 1,
            "Unsupported suite version")
    require(isinstance(suite["cases"], list) and suite["cases"], "Cases must be nonempty")
    case_ids = set()
    for case in suite["cases"]:
        fields(case, {"id", "prompt", "assertions"}, {"should_trigger"})
        require(valid_id(case["id"]) and case["id"] not in case_ids, "Invalid/duplicate case ID")
        case_ids.add(case["id"])
        require(nonblank(case["prompt"]), "Prompt must be nonblank")
        if "should_trigger" in case:
            require(type(case["should_trigger"]) is bool, "should_trigger must be boolean")
        require(isinstance(case["assertions"], list) and case["assertions"],
                "Assertions must be nonempty")
        assertion_ids = set()
        for assertion in case["assertions"]:
            require(isinstance(assertion, dict), "Assertion must be an object")
            kind = assertion.get("type")
            require(isinstance(kind, str) and kind in TYPES, "Unknown assertion type")
            required = {"id", "type"}
            optional = {"description"}
            if kind in STRING_TYPES | FILE_TYPES:
                required.add("file")
            if kind in STRING_TYPES:
                required.add("value")
                optional.add("case_sensitive")
            fields(assertion, required, optional)
            require(valid_id(assertion["id"]) and assertion["id"] not in assertion_ids,
                    "Invalid/duplicate assertion ID")
            assertion_ids.add(assertion["id"])
            if "description" in assertion:
                require(nonblank(assertion["description"]), "Description must be nonblank")
            if "file" in assertion:
                require(valid_path(assertion["file"]), "Unsafe relative file path")
            if kind in STRING_TYPES:
                require(nonblank(assertion["value"]), "String value must be nonblank")
                require(type(assertion.get("case_sensitive", True)) is bool,
                        "case_sensitive must be boolean")
            if kind == "trigger":
                require("should_trigger" in case, "Trigger assertion needs should_trigger")
    return suite


def suite_hash(suite):
    data = json.dumps(suite, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def validate_manual(manual, suite):
    if manual is None:
        return {}
    fields(manual, {"schema_version", "records"})
    require(type(manual["schema_version"]) is int and manual["schema_version"] == 1,
            "Unsupported manual version")
    require(isinstance(manual["records"], list), "Manual records must be an array")
    known = {(c["id"], a["id"]) for c in suite["cases"] for a in c["assertions"]
             if a["type"] in MANUAL_TYPES}
    records = {}
    for record in manual["records"]:
        fields(record, {"case_id", "assertion_id", "status", "reviewer", "evidence"})
        require(valid_id(record["case_id"]) and valid_id(record["assertion_id"]),
                "Invalid manual record IDs")
        key = (record["case_id"], record["assertion_id"])
        require(key in known and key not in records, "Unknown/duplicate manual assertion")
        require(isinstance(record["status"], str) and record["status"] in {"pass", "fail"},
                "Manual status must be pass or fail")
        require(nonblank(record["reviewer"]) and nonblank(record["evidence"]),
                "Manual evidence and reviewer are required")
        records[key] = record
    return records


def counts(statuses):
    result = {s: statuses.count(s) for s in ("pass", "fail", "not_run")}
    total = len(statuses)
    checked = result["pass"] + result["fail"]
    result.update(total=total, checked=checked,
                  pass_rate=result["pass"] / checked if checked else None,
                  coverage=checked / total if total else 0.0)
    return result


def overall(statuses):
    return "fail" if "fail" in statuses else "not_run" if "not_run" in statuses else "pass"


def safe_path(root, parts):
    """Reject symlinks without following them, including broken symlinks."""
    current = root
    require(not current.is_symlink(), "Symlink evidence root")
    for part in parts:
        current = current / part
        require(not current.is_symlink(), "Symlink evidence path")
    return current


def check_assertion(root, case, assertion, records):
    kind = assertion["type"]
    result = {"id": assertion["id"], "type": kind, "status": "not_run",
              "evidence": "", "evidence_kind": "missing"}
    try:
        case_path = safe_path(root, [case["id"]])
        if not case_path.is_dir():
            result["evidence"] = "Saved case output directory is missing or not a directory"
            return result
        if kind in MANUAL_TYPES:
            record = records.get((case["id"], assertion["id"]))
            if record:
                result.update(status=record["status"], evidence=record["evidence"],
                              evidence_kind="manual", reviewer=record["reviewer"])
            else:
                result["evidence"] = "No attributed manual evidence supplied"
            return result
        path = safe_path(root, [case["id"]] + assertion["file"].split("/"))
        if kind == "required_file":
            passed = path.is_file()
            evidence = "Regular file exists" if passed else "Required regular file missing"
        elif kind == "forbidden_file":
            passed = not path.exists()
            evidence = "Forbidden path absent" if passed else "Forbidden path exists"
        else:
            if not path.is_file():
                result["evidence"] = "Text evidence file missing or not a regular file"
                return result
            # Bound the read, even if the evidence file changes after the size check.
            with path.open("rb") as handle:
                data = handle.read(MAX_TEXT_BYTES + 1)
            if len(data) > MAX_TEXT_BYTES:
                result["evidence"] = "Text evidence exceeds 8 MiB"
                return result
            text = data.decode("utf-8")
            value = assertion["value"]
            if not assertion.get("case_sensitive", True):
                text, value = text.casefold(), value.casefold()
            found = value in text
            passed = found if kind == "required_string" else not found
            evidence = "Literal substring " + ("present" if found else "absent")
        result.update(status="pass" if passed else "fail", evidence=evidence,
                      evidence_kind="deterministic")
    except (OSError, UnicodeError, ValueError) as exc:
        result["evidence"] = "Evidence unavailable: " + str(exc)
    return result


def evaluate(suite, outputs, label, manual=None):
    validate_suite(suite)
    require(nonblank(label), "Label must be nonblank")
    records = validate_manual(manual, suite)
    root = Path(os.path.abspath(outputs))
    cases = []
    for case in suite["cases"]:
        assertions = [check_assertion(root, case, a, records) for a in case["assertions"]]
        statuses = [a["status"] for a in assertions]
        cases.append({"id": case["id"], "status": overall(statuses),
                      "counts": counts(statuses), "assertions": assertions})
    statuses = [a["status"] for c in cases for a in c["assertions"]]
    return {"result_version": 1, "suite_sha256": suite_hash(suite), "label": label,
            "outputs_root": str(root), "status": overall(statuses),
            "counts": counts(statuses), "cases": cases}


def validate_result(result):
    fields(result, {"result_version", "suite_sha256", "label", "outputs_root",
                    "status", "counts", "cases"})
    require(type(result["result_version"]) is int and result["result_version"] == 1,
            "Unsupported result version")
    require(isinstance(result["suite_sha256"], str) and
            re.fullmatch(r"[a-f0-9]{64}", result["suite_sha256"]), "Invalid suite fingerprint")
    require(nonblank(result["label"]) and nonblank(result["outputs_root"]), "Invalid result label/root")
    require(isinstance(result["cases"], list) and result["cases"], "Missing result cases")
    all_statuses, case_ids = [], set()
    for case in result["cases"]:
        fields(case, {"id", "status", "counts", "assertions"})
        require(valid_id(case["id"]) and case["id"] not in case_ids, "Invalid/duplicate result case")
        case_ids.add(case["id"])
        require(isinstance(case["assertions"], list) and case["assertions"], "Missing result assertions")
        statuses, ids = [], set()
        for a in case["assertions"]:
            fields(a, {"id", "type", "status", "evidence", "evidence_kind"}, {"reviewer"})
            require(valid_id(a["id"]) and a["id"] not in ids, "Invalid/duplicate result assertion")
            ids.add(a["id"])
            require(isinstance(a["type"], str) and a["type"] in TYPES, "Invalid result type")
            require(isinstance(a["status"], str) and a["status"] in STATUSES, "Invalid result status")
            require(nonblank(a["evidence"]), "Missing result evidence")
            expected_kind = ("missing" if a["status"] == "not_run" else
                             "manual" if a["type"] in MANUAL_TYPES else "deterministic")
            require(a["evidence_kind"] == expected_kind, "Inconsistent evidence kind")
            if expected_kind == "manual":
                require(nonblank(a.get("reviewer")), "Missing reviewer")
            else:
                require("reviewer" not in a, "Reviewer on nonmanual result")
            statuses.append(a["status"])
        require(case["counts"] == counts(statuses) and case["status"] == overall(statuses),
                "Inconsistent case counts/status")
        all_statuses.extend(statuses)
    require(result["counts"] == counts(all_statuses) and
            result["status"] == overall(all_statuses), "Inconsistent result counts/status")
    return result


def index_result(result):
    validate_result(result)
    return {(c["id"], a["id"]): a for c in result["cases"] for a in c["assertions"]}


def matched_indexes(results):
    require(bool(results), "At least one result is required")
    indexes = [index_result(r) for r in results]
    for result, index in zip(results[1:], indexes[1:]):
        require(result["suite_sha256"] == results[0]["suite_sha256"],
                "Different suites are not comparable")
        require(index.keys() == indexes[0].keys() and
                all(index[k]["type"] == indexes[0][k]["type"] for k in index),
                "Result assertion shapes differ")
    return indexes


def compare(baseline, candidate):
    left, right = matched_indexes([baseline, candidate])
    rows, paired_left, paired_right = [], [], []
    for key, a in left.items():
        b = right[key]
        checked = a["status"] != "not_run" and b["status"] != "not_run"
        rows.append({"case_id": key[0], "assertion_id": key[1], "type": a["type"],
                     "baseline": a["status"], "candidate": b["status"],
                     "paired_checked": checked})
        if checked:
            paired_left.append(a["status"])
            paired_right.append(b["status"])
    b_counts, c_counts = counts(paired_left), counts(paired_right)
    delta = (c_counts["pass_rate"] - b_counts["pass_rate"]) if paired_left else None
    return {"suite_sha256": baseline["suite_sha256"],
            "baseline": {"label": baseline["label"], "counts": baseline["counts"]},
            "candidate": {"label": candidate["label"], "counts": candidate["counts"]},
            "paired": {"checked": len(paired_left), "baseline": b_counts,
                       "candidate": c_counts, "pass_rate_delta": delta},
            "transitions": rows}


def summarize(results):
    matched_indexes(results)
    require(all(r["label"] == results[0]["label"] for r in results),
            "Repeated summaries require the same label")
    rates = [r["counts"]["pass_rate"] for r in results if r["counts"]["pass_rate"] is not None]
    statuses = [a["status"] for r in results for c in r["cases"] for a in c["assertions"]]
    return {"suite_sha256": results[0]["suite_sha256"], "label": results[0]["label"],
            "run_count": len(results), "runs": [r["counts"] for r in results],
            "pooled_counts": counts(statuses), "observed_rate_count": len(rates),
            "mean_pass_rate": statistics.mean(rates) if rates else None,
            "sample_stddev_pass_rate": statistics.stdev(rates) if len(rates) > 1 else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("evaluate", help="Check saved output artifacts")
    run.add_argument("--cases", required=True)
    run.add_argument("--outputs", required=True)
    run.add_argument("--label", required=True)
    run.add_argument("--manual")
    comparison = sub.add_parser("compare", help="Compare identical suites")
    comparison.add_argument("baseline")
    comparison.add_argument("candidate")
    summary = sub.add_parser("summarize", help="Summarize existing repeated results")
    summary.add_argument("results", nargs="+")
    for child in (run, comparison, summary):
        child.add_argument("--out", help="JSON destination; parent directory must exist")
    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate(load_json(args.cases), args.outputs, args.label,
                              load_json(args.manual) if args.manual else None)
            inputs = [args.cases] + ([args.manual] if args.manual else [])
        elif args.command == "compare":
            result = compare(load_json(args.baseline), load_json(args.candidate))
            inputs = [args.baseline, args.candidate]
        else:
            paths = [Path(p).resolve() for p in args.results]
            require(len(set(paths)) == len(paths), "Duplicate result paths")
            result = summarize([load_json(p) for p in paths])
            inputs = args.results
        if args.out:
            destination = Path(args.out).resolve()
            require(destination not in {Path(p).resolve() for p in inputs},
                    "Output would overwrite an input")
            if args.command == "evaluate":
                root = Path(args.outputs).resolve()
                require(destination != root and root not in destination.parents,
                        "Output must be outside the evidence root")
            destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, TypeError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
