#!/usr/bin/env python3

"""
Step 4: Security & Reliability Testing - Fuzzing
------------------------------------------------
Modifications:
  - Outputs artifacts into ./test_artifacts/ so analyze_results.py can parse them.

Usage:
  python3 fuzz_test.py
"""

import os
import random
import subprocess
import time

# If you want to automatically build first, set to True and update the path:
AUTO_BUILD = False
BUILD_SCRIPT = "./build_and_run.py"  # Or the path to your Step 3 script

# Where is your QEMU kernel after building?
FIRMWARE_PATH = "/home/arampour/FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC/build/gcc/output/RTOSDemo.out"

# Directory to store fuzz inputs and logs
TEST_ARTIFACTS_DIR = "test_artifacts"
NUM_ITERATIONS = 10

def build_firmware_if_needed():
    """
    (Optional) Call your Step 3 build script to ensure code is up to date.
    """
    if AUTO_BUILD:
        print("Auto-building firmware using build_and_run.py (but not running it).")
        result = subprocess.run([BUILD_SCRIPT], capture_output=True, text=True)
        if result.returncode != 0:
            print("Build failed, cannot proceed with fuzzing.")
            print(result.stdout)
            print(result.stderr)
            exit(1)
        else:
            print("Build succeeded, continuing to fuzzing...")

def create_random_data(max_size=512):
    """
    Returns a randomly sized bytes object, sometimes exceeding max_size to test boundary checks.
    """
    size = random.randint(1, max_size * 2)  # occasionally exceed expected
    return bytes([random.randint(0, 255) for _ in range(size)])

def fuzz_once(iteration):
    """
    1. Generate random input.
    2. Launch QEMU, pass data to the firmware.
    3. Capture output for anomalies, store logs in test_artifacts/.
    """
    fuzz_data = create_random_data()

    # Ensure the artifacts directory exists
    os.makedirs(TEST_ARTIFACTS_DIR, exist_ok=True)

    # Save the fuzz input for reference
    input_filename = os.path.join(TEST_ARTIFACTS_DIR, f"fuzz_input_{iteration}.bin")
    with open(input_filename, "wb") as f:
        f.write(fuzz_data)

    print(f"[Iteration {iteration}] Starting QEMU with {len(fuzz_data)} bytes of fuzz data...")

    qemu_cmd = [
        "qemu-system-arm",
        "-M", "mps2-an385",
        "-kernel", FIRMWARE_PATH,
        "-serial", "stdio",
        "-nographic"
    ]

    proc = subprocess.Popen(
        qemu_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        out, err = proc.communicate(
            input=fuzz_data.decode('latin-1', errors='ignore'),
            timeout=5
        )
    except subprocess.TimeoutExpired:
        print(f"[Iteration {iteration}] QEMU timed out. Potential freeze/DoS scenario.")
        proc.kill()
        out, err = proc.communicate()

    # Look for anomaly keywords
    anomalies = []
    triggers = ["overflow", "assert", "hard fault", "malloc failed", "crash", "stack overflow", "error"]
    out_lower = out.lower()
    err_lower = err.lower()
    for trig in triggers:
        if trig in out_lower or trig in err_lower:
            anomalies.append(trig)

    if anomalies:
        print(f"[Iteration {iteration}] Detected anomalies: {anomalies}")
        log_filename = os.path.join(TEST_ARTIFACTS_DIR, f"fuzz_crashlog_{iteration}.txt")
        with open(log_filename, "w") as lf:
            lf.write("=== STDOUT ===\n")
            lf.write(out)
            lf.write("\n=== STDERR ===\n")
            lf.write(err)
    else:
        print(f"[Iteration {iteration}] No anomalies detected.")

def main():
    build_firmware_if_needed()

    for i in range(NUM_ITERATIONS):
        time.sleep(1)  # small delay between runs
        fuzz_once(i)

    print("Fuzz testing complete. Check test_artifacts/ for logs or anomalies.")

if __name__ == "__main__":
    main()
