#!/usr/bin/env python3

"""
Step 3: Integration & Build with FreeRTOS

This script:
1. Calls 'make' in the specified build directory to compile the FreeRTOS QEMU demo.
2. Runs the resulting RTOSDemo.out under QEMU, printing console output.

Adjust 'BUILD_DIR' or 'QEMU_KERNEL' below if your build artifacts differ.
"""

import subprocess
import sys
import os

# Path to the directory where your FreeRTOS demo gets built.
BUILD_DIR = "/home/arampour/FreeRTOS/FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC/build/gcc"

# Relative path (inside BUILD_DIR) to the compiled ELF.
QEMU_KERNEL = "output/RTOSDemo.out"

def build_firmware():
    """
    Run 'make' in the BUILD_DIR to compile the project.
    """
    print(f"Building firmware in {BUILD_DIR} ...")
    result = subprocess.run(["make", "-j"], cwd=BUILD_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print("Build failed:\n")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    else:
        print("Build succeeded.")
        print(result.stdout)

def run_qemu():
    """
    Launch QEMU to run the newly built firmware, routing output to the console.
    """
    qemu_cmd = [
        "qemu-system-arm",
        "-M", "mps2-an385",
        "-kernel", QEMU_KERNEL,
        "-serial", "mon:stdio",
        "-nographic",
    ]

    print(f"Running QEMU with kernel: {QEMU_KERNEL}\n")
    process = subprocess.Popen(qemu_cmd, cwd=BUILD_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        # Stream QEMU's stdout to our console
        for line in process.stdout:
            print(line, end="")
    except KeyboardInterrupt:
        # If user hits Ctrl+C, stop QEMU gracefully
        pass

    # Terminate QEMU (if still running)
    process.kill()
    out, err = process.communicate()

    print("\nQEMU finished.")
    if err:
        print("Error output:\n", err)

def main():
    build_firmware()
    run_qemu()

if __name__ == "__main__":
    main()
