# Running with VSCode Launch Configurations

## Prerequisites
* Install [C/C++ extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode.cpptools) in VSCode.
* Install [arm-none-eabi-gcc](https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-rm/downloads).
* Install GNU make utility.
* Ensure the required binaries are in PATH with ```arm-none-eabi-gcc --version```, ```arm-none-eabi-gdb --version```, and ```make --version```.

## Building and Running
1. Open VSCode to the folder ```FreeRTOS/Demo/CORTEX_MPS2_QEMU_IAR_GCC```.
2. Open ```.vscode/launch.json```, and ensure the ```miDebuggerPath``` variable is set to the path where arm-none-eabi-gdb is on your machine.
3. Open ```main.c```, and set ```mainCREATE_SIMPLE_BLINKY_DEMO_ONLY``` to ```1``` to generate just the [simply blinky demo](https://www.freertos.org/a00102.html#simple_blinky_demo).
4. On the VSCode left side panel, select the “Run and Debug” button. Then select “Launch QEMU RTOSDemo” from the dropdown on the top right and press the play button. This will build, run, and attach a debugger to the demo program.

## Tracing with Percepio View
This demo project includes Percepio TraceRecorder, configured for snapshot tracing with Percepio View or Tracealyzer.
Percepio View is a free tracing tool from Percepio, providing the core features of Percepio Tracealyzer but limited to snapshot tracing.
No license or registration is required. More information and download is found at [Percepio's product page for Percepio View](https://traceviewer.io/get-view?target=freertos).

### TraceRecorder Integration
If you like to study how TraceRecorder is integrated, the steps for adding TraceRecorder are tagged with "TODO TraceRecorder" comments in the demo source code.
This way, if using an Eclipse-based IDE, you can find a summary in the Tasks window by selecting Window -> Show View -> Tasks (or Other, if not listed).
See also [the official getting-started guide](https://traceviewer.io/getting-started-freertos-view).

### Usage with GDB
To save the TraceRecorder trace, start a debug session with GDB.
Halt the execution and the run the command below. 
This saves the trace as trace.bin in the build/gcc folder.
Open the trace file in Percepio View or Tracealyzer.

If using an Eclipse-based IDE, run the following command in the "Debugger Console":
```
dump binary value trace.bin *RecorderDataPtr
```

If using VS Code, use the "Debug Console" and add "-exec" before the command:
```
-exec dump binary value trace.bin *RecorderDataPtr
```

Note that you can typically copy/paste this command into the debug console.


### Usage with IAR Embedded Workbench for Arm
Launch the IAR debugger. With the default project configuration, this should connect to the QEMU GDB server.
To save the trace, please refer to the "Snapshot Mode" guide at [https://percepio.com/iar](https://percepio.com/iar).
In summary:
- Download the IAR macro file [save_trace_buffer.mac](https://percepio.com/downloads/save_trace_buffer.mac) (click "save as")
- Add the macro file in the project options -> Debugger -> Use Macro File(s). 
- Start debugging and open View -> Macros -> Debugger Macros.
- Locate and run "save_trace_buffer". Open the resulting "trace.hex" in Percepio View or Tracealyzer.



To tie everything together—your Securing-LLM-Generated-Embedded-Firmware scripts, FreeRTOS kernel, and QEMU—you’ll want one unified project directory that:

1. **Holds the FreeRTOS port**,
2. **Contains your GPT-4–generated MQTT tasks**,
3. **Includes your automation scripts** (`build_and_run.py`, `fuzz_test.py`, etc.),
4. **Defines a Makefile** that builds both kernel and app for ARM, and
5. **Uses a single QEMU invocation** to run the built firmware.

Below is a skeleton layout and the minimal edits you need:

---

## 1. Project Layout

```
Securing-LLM-Embedded/
├── FreeRTOS-Kernel/                      ← clone of FreeRTOS-Kernel repo
│   ├── include/
│   ├── Source/
│   └── portable/GCC/ARM_CM3/             ← Cortex-M3 port
├── Inc/                                  ← your headers
│   ├── FreeRTOSConfig.h
│   └── mqtt_task.h                       ← from generate_freertos_task.py
├── Src/                                  ← your C source files
│   ├── main.c
│   └── mqtt_task.c                       ← from generate_freertos_task.py
├── scripts/                              ← your Python tooling
│   ├── generate_freertos_task.py
│   ├── build_and_run.py
│   ├── static_analysis.py
│   ├── fuzz_test.py
│   ├── analyze_results.py
│   └── llm_refine.py
├── Makefile                              ← builds FreeRTOS + your app
├── stm32_flash.ld                        ← link script for Cortex-M3 (copy from demo)
└── README.md
```

---

## 2. Makefile: Building Kernel + App

```makefile
# Toolchain
CC        := arm-none-eabi-gcc
OBJCOPY   := arm-none-eabi-objcopy

# CPU & flags
MCU_FLAGS := -mcpu=cortex-m3 -mthumb -O2 -ffunction-sections -fdata-sections
INCLUDES  := -IFreeRTOS-Kernel/include \
             -IFreeRTOS-Kernel/portable/GCC/ARM_CM3 \
             -IInc

# Sources
FRTOS_SRC := FreeRTOS-Kernel/Source/*.c \
             FreeRTOS-Kernel/portable/GCC/ARM_CM3/port.c
APP_SRC   := Src/main.c Src/mqtt_task.c

# Objects
OBJS      := $(patsubst %.c,%.o,$(notdir $(FRTOS_SRC))) \
             main.o mqtt_task.o

all: firmware.bin

%.o: FreeRTOS-Kernel/Source/%.c
	$(CC) $(MCU_FLAGS) $(INCLUDES) -c $< -o $@

port.o: FreeRTOS-Kernel/portable/GCC/ARM_CM3/port.c
	$(CC) $(MCU_FLAGS) $(INCLUDES) -c $< -o $@

main.o: Src/main.c
	$(CC) $(MCU_FLAGS) $(INCLUDES) -c $< -o $@

mqtt_task.o: Src/mqtt_task.c
	$(CC) $(MCU_FLAGS) $(INCLUDES) -c $< -o $@

firmware.elf: $(OBJS)
	$(CC) $(MCU_FLAGS) -Tstm32_flash.ld -Wl,--gc-sections $^ -o $@

firmware.bin: firmware.elf
	$(OBJCOPY) -O binary firmware.elf firmware.bin

clean:
	rm -f *.o firmware.elf firmware.bin
```

> **Note:** Adjust `stm32_flash.ld` to your memory map or use the one in the FreeRTOS demo you chose.

---

## 3. Automating Build + QEMU Run

Edit your **`build_and_run.py`** (in `scripts/`) to:

1. **Call** `make all` in the project root.
2. **Launch QEMU** with the same `-M lm3s811evb` (or whichever board matches your port) and `-kernel firmware.bin`, redirecting serial to stdout.

Example snippet inside `build_and_run.py`:

```python
import subprocess, os

# 1. Build
subprocess.run(["make", "all"], check=True)

# 2. Run in QEMU
qemu_cmd = [
    "qemu-system-arm",
    "-M", "lm3s811evb",
    "-kernel", "firmware.bin",
    "-nographic",
    "-serial", "mon:stdio"
]
subprocess.run(qemu_cmd)
```

---

## 4. Hooking in Static Analysis & Fuzzing

In your **`static_analysis.py`**, point it at `Src/` and `Inc/`:

```python
# Example Cppcheck call
cmd = [
  "cppcheck",
  "--enable=all",
  "--force",
  "-IInc",
  "-IFreeRTOS-Kernel/include",
  "Src"
]
subprocess.run(cmd)
```

In **`fuzz_test.py`**, ensure the `--qemu-cmd` you pass matches the QEMU invocation in `build_and_run.py` (so AFL++ runs the same firmware in QEMU user or system mode).

---

## 5. End-to-End Script

Create a wrapper `run_pipeline.sh` (in WSL/Ubuntu shell) to sequentially:

```bash
#!/bin/bash
# 1. Generate MQTT task
python3 scripts/generate_freertos_task.py \
  --output Src/mqtt_task.c \
  --prompt-file scripts/mqtt_prompt.txt

# 2. Build & Run (smoke-test)
python3 scripts/build_and_run.py

# 3. Static analysis
python3 scripts/static_analysis.py --out results/static.json

# 4. Fuzz testing
python3 scripts/fuzz_test.py --out results/fuzz --seed seeds

# 5. Analyze results
python3 scripts/analyze_results.py \
  --static results/static.json \
  --fuzz-dir results/fuzz \
  --out results/summary.json

# 6. Auto-patch via LLM
python3 scripts/llm_refine.py \
  --summary results/summary.json \
  --src-dir Src \
  --out patches/
```

Each iteration of this script:

1. **Regenerates** (or refines) the MQTT code,
2. **Rebuilds** in FreeRTOS + QEMU,
3. **Re-analyzes** with Cppcheck/AFL++,
4. **Feeds back** into GPT-4 for patches.

---

With this combined structure:

* Your **FreeRTOS kernel** and **app code** live side-by-side.
* **Makefile** builds everything for ARM.
* **`build_and_run.py`** and **QEMU** let you emulate the target.
* **Static/fuzz** scripts automate testing.
* **`llm_refine.py`** closes the loop.




