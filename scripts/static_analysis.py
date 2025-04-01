#!/usr/bin/env python3

"""
Step 4: Security & Reliability Testing - Static Analysis
--------------------------------------------------------
Modifications:
  - Outputs analysis results into test_artifacts/static_analysis/ 
    so analyze_results.py can parse them.

Usage:
  python3 static_analysis.py
"""

import os
import subprocess
import shutil

SOURCE_PATHS = [
    "/home/arampour/FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC",
    # "/home/arampour/FreeRTOS/FreeRTOS/Source"  # optional, if you want to scan core kernel
]

# Directory to store static analysis logs
STATIC_OUT_DIR = "test_artifacts/static_analysis"

def clear_old_static_logs():
    """
    Removes old static analysis logs (e.g., .txt, .log) from STATIC_OUT_DIR 
    before running a new static analysis.
    """
    if os.path.isdir(STATIC_OUT_DIR):
        for fname in os.listdir(STATIC_OUT_DIR):
            if fname.endswith(".txt") or fname.endswith(".log"):
                os.remove(os.path.join(STATIC_OUT_DIR, fname))
    else:
        print(f"[INFO] Directory '{STATIC_OUT_DIR}' does not exist; no old logs to clear.")


def run_cppcheck():
    print("Running Cppcheck analysis...\n")
    os.makedirs(STATIC_OUT_DIR, exist_ok=True)

    cppcheck_log = os.path.join(STATIC_OUT_DIR, "cppcheck_report.txt")

    with open(cppcheck_log, "w") as log_file:
        for path in SOURCE_PATHS:
            cmd = [
                "cppcheck",
                "--enable=all",
                "--inconclusive",
                "--force",
                path
            ]
            print(f"Analyzing path: {path}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            log_file.write(f"----- Analysis of {path} -----\n")
            log_file.write(result.stdout)
            log_file.write("\n")
            if result.stderr:
                log_file.write("Cppcheck Errors:\n")
                log_file.write(result.stderr)
                log_file.write("\n")

    print(f"Cppcheck results saved to: {cppcheck_log}")

def run_clang_static_analyzer():
    print("\nRunning Clang Static Analyzer (scan-build)...\n")
    os.makedirs(STATIC_OUT_DIR, exist_ok=True)

    scanbuild_log = os.path.join(STATIC_OUT_DIR, "clang_scanbuild_results.txt")

    build_dir = "/home/arampour/FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC/build/gcc"
    cmd = [
        "scan-build",
        "--use-cc=clang",
        "--use-c++=clang++",
        "make",
        "-j"
    ]

    with open(scanbuild_log, "w") as log_file:
        result = subprocess.run(cmd, cwd=build_dir, capture_output=True, text=True)
        log_file.write(result.stdout)
        if result.stderr:
            log_file.write("Scan-Build Errors:\n")
            log_file.write(result.stderr)
            log_file.write("\n")

    print(f"Clang scan-build results saved to: {scanbuild_log}")

def main():
    clear_old_static_logs()

    # Use whichever analyzers you prefer
    run_cppcheck()
    run_clang_static_analyzer()
    print("Static analysis complete. Check test_artifacts/static_analysis/ for logs.")

if __name__ == "__main__":
    main()
