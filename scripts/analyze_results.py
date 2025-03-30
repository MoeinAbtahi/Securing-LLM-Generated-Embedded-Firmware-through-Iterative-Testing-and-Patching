#!/usr/bin/env python3

"""
Step 5: Analysis of Results
---------------------------
Parses logs from fuzz_test.py and static_analysis.py to locate error indicators.
Correlates each with a threat category/CWE (from Step 1).

Outputs:
  - A JSON report (analysis_report.json) in test_artifacts/
  - A console summary

Usage:
  python3 analyze_results.py
"""

import os
import json

# Directory where fuzz logs and static analysis logs are stored
TEST_ARTIFACTS_DIR = "test_artifacts"
FUZZ_PREFIX = "fuzz_crashlog_"
STATIC_ANALYSIS_DIR = "static_analysis"

# Map keywords to threats & CWE IDs
THREAT_KEYWORDS = {
    "overflow": {
        "threat": "Buffer Overflow",
        "cwe": "CWE-120: Classic Buffer Overflow"
    },
    "stack overflow": {
        "threat": "Buffer Overflow",
        "cwe": "CWE-120: Classic Buffer Overflow"
    },
    "hard fault": {
        "threat": "Potential Crash or Memory Fault",
        "cwe": "CWE-730: Null Pointer or System Crash"
    },
    "race condition": {
        "threat": "Concurrency Issue",
        "cwe": "CWE-362: Race Condition"
    },
    "assert": {
        "threat": "Assertion Failure",
        "cwe": "N/A"
    },
    "dos": {
        "threat": "Denial of Service",
        "cwe": "CWE-400: Uncontrolled Resource Consumption"
    },
    "missed deadline": {
        "threat": "Real-Time Violation",
        "cwe": "CWE-400: Uncontrolled Resource Consumption"
    },
    "malloc failed": {
        "threat": "Memory Allocation Failure",
        "cwe": "CWE-401: Memory Leak or Resource Exhaustion"
    },
    "error": {
        "threat": "Generic Error",
        "cwe": "N/A"
    }
}

def parse_file_for_threats(filepath):
    """
    Reads file line by line, searching for known error keywords.
    Returns a list of discovered vulnerabilities, each as a dict:
      {
        "file": <filename>,
        "line": <line number>,
        "keyword": <keyword found>,
        "threat": <threat category>,
        "cwe": <cwe string>,
        "line_text": <the log line>
      }
    """
    vulnerabilities = []
    if not os.path.isfile(filepath):
        return vulnerabilities

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        line_lower = line.lower()
        for keyword, info in THREAT_KEYWORDS.items():
            if keyword in line_lower:
                vulnerabilities.append({
                    "file": os.path.basename(filepath),
                    "line": i + 1,
                    "keyword": keyword,
                    "threat": info["threat"],
                    "cwe": info["cwe"],
                    "line_text": line.strip()
                })
    return vulnerabilities

def analyze_fuzz_logs(results):
    """
    Searches for fuzz_crashlog_*.txt files in test_artifacts/ and parses them.
    """
    if not os.path.isdir(TEST_ARTIFACTS_DIR):
        return

    for fname in os.listdir(TEST_ARTIFACTS_DIR):
        if fname.startswith(FUZZ_PREFIX) and fname.endswith(".txt"):
            full_path = os.path.join(TEST_ARTIFACTS_DIR, fname)
            vulns = parse_file_for_threats(full_path)
            results.extend(vulns)

def analyze_static_analysis_logs(results):
    """
    Looks in test_artifacts/static_analysis/ for typical logs 
    (cppcheck_report.txt, clang_scanbuild_results.txt).
    """
    analysis_dir = os.path.join(TEST_ARTIFACTS_DIR, STATIC_ANALYSIS_DIR)
    if not os.path.isdir(analysis_dir):
        return

    for fname in os.listdir(analysis_dir):
        if fname.endswith(".txt") or fname.endswith(".log"):
            full_path = os.path.join(analysis_dir, fname)
            vulns = parse_file_for_threats(full_path)
            results.extend(vulns)

def main():
    results = []

    # 1. Collect fuzz logs
    analyze_fuzz_logs(results)

    # 2. Collect static analysis logs
    analyze_static_analysis_logs(results)

    # 3. If you store any QEMU console output in test_artifacts/console_log.txt,
    #    you can parse that too with parse_file_for_threats.

    if not results:
        print("No vulnerabilities or errors found in logs.")
        return

    # Create a final JSON report
    report_path = os.path.join(TEST_ARTIFACTS_DIR, "analysis_report.json")
    with open(report_path, "w", encoding="utf-8") as rf:
        json.dump(results, rf, indent=2)

    print(f"Discovered {len(results)} potential issues. Detailed report in {report_path}\n")

    # Print a console summary
    for i, item in enumerate(results, start=1):
        print(f"Issue #{i}:")
        print(f"  File: {item['file']} (Line {item['line']})")
        print(f"  Keyword: {item['keyword']}")
        print(f"  Threat: {item['threat']}")
        print(f"  CWE: {item['cwe']}")
        print(f"  Context: \"{item['line_text']}\"")
        print("")

if __name__ == "__main__":
    main()
