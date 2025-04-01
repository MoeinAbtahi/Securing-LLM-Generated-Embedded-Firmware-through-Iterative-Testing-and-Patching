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
import shutil

# If you want to automatically build first, set to True and update the path:
AUTO_BUILD = False
BUILD_SCRIPT = "./build_and_run.py"  # Or the path to your Step 3 script

# Where is your QEMU kernel after building?
FIRMWARE_PATH = "/home/arampour/FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC/build/gcc/output/RTOSDemo.out"

# Directory to store fuzz inputs and logs
TEST_ARTIFACTS_DIR = "test_artifacts"
NUM_ITERATIONS = 10

def clear_old_logs():
    """
    Removes old fuzz logs and input files from test_artifacts/ before
    starting a new fuzz test run.
    """
    if os.path.isdir(TEST_ARTIFACTS_DIR):
        for fname in os.listdir(TEST_ARTIFACTS_DIR):
            # Remove old fuzz inputs and logs
            if (fname.startswith("fuzz_crashlog_") or
                fname.startswith("fuzz_freezelog_") or
                fname.startswith("fuzz_input_")):
                os.remove(os.path.join(TEST_ARTIFACTS_DIR, fname))
    else:
        print(f"[INFO] Directory '{TEST_ARTIFACTS_DIR}' does not exist; no old logs to clear.")

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
    1. Generate random input
    2. Launch QEMU
    3. Check output only for 'Deadline Missed'
    """
    fuzz_data = create_random_data()

    input_filename = os.path.join(TEST_ARTIFACTS_DIR, f"fuzz_input_{iteration}.bin")
    with open(input_filename, "wb") as f:
        f.write(fuzz_data)

    print(f"[Iteration {iteration}] Starting QEMU with {len(fuzz_data)} bytes of fuzz data...")

    qemu_cmd = [
        "qemu-system-arm",
        "-machine", "mps2-an385",            # MPS2-AN385 board
        "-cpu", "cortex-m3",                # Explicitly select the CPU core
        "-kernel", FIRMWARE_PATH,           # Your firmware ELF/AXF/OUT
        "-monitor", "none",                 # Disable QEMU monitor
        "-nographic",                       # No graphical window
        "-semihosting",                     # Enable semihosting
        "-semihosting-config", "enable=on,target=native", 
        "-serial", "stdio"                  # Send UART output to stdio
    ]

    proc = subprocess.Popen(
        qemu_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        # If your firmware doesn't actually read from stdin,
        # passing fuzz_data won't matter. But let's keep it:
        #out, err = proc.communicate("HelloX", timeout = 5)  # for instance
        number = random.randint(1, 5)
        out, err = proc.communicate(
            input=fuzz_data.decode('latin-1', errors='ignore'),
            timeout=number
        )
    except subprocess.TimeoutExpired:
        #print(f"[Iteration {iteration}] QEMU timed out. Potential freeze.")
        proc.kill()
        out, err = proc.communicate()

        # Create a separate freeze log
        #freeze_log_filename = os.path.join(TEST_ARTIFACTS_DIR, f"fuzz_freezelog_{iteration}.txt")
        #with open(freeze_log_filename, "w") as lf:
        #    lf.write(f"[Iteration {iteration}] QEMU freeze or timeout detected.\n")
        #    lf.write("=== STDOUT ===\n")
        #    lf.write(out)
        #    lf.write("\n=== STDERR ===\n")

    # We only look for "Deadline Missed"
    out_lower = out.lower()
    err_lower = err.lower()
    #print(out_lower)
    if "missed deadline" in out_lower or "missed deadline" in err_lower:
        print(f"[Iteration {iteration}] Detected missed deadline!")
        log_filename = os.path.join(TEST_ARTIFACTS_DIR, f"fuzz_crashlog_{iteration}.txt")
        with open(log_filename, "w") as lf:
            lf.write("=== STDOUT ===\n")
            lf.write(out)
            lf.write("\n=== STDERR ===\n")
            lf.write(err)
    else:
        print(f"[Iteration {iteration}] No missed deadline detected.")


def main():
    build_firmware_if_needed()

    clear_old_logs()

    for i in range(NUM_ITERATIONS):
        time.sleep(1)  # small delay between runs
        fuzz_once(i)

    print("Fuzz testing complete. Check test_artifacts/ for logs or anomalies.")

if __name__ == "__main__":
    main()
