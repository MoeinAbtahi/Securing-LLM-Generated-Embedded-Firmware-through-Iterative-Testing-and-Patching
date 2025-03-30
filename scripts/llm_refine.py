#!/usr/bin/env python3

"""
Step 6: Automated (or Manual) Refinement via the LLM (GPT-4)
------------------------------------------------------------
This script:
 1. Reads the "analysis_report.json" from Step 5.
 2. For each discovered vulnerability, prompts GPT-4 for a recommended fix.
 3. Prints or stores suggested patches. 
 4. Optionally applies each suggestion automatically to the target C file (e.g. main.c).
    - This is a naive approach: we parse a code block from the LLM's text and replace
      the old snippet with the new snippet. Adjust it for your real environment as needed.

Usage:
  1. Set your OPENAI_API_KEY environment variable:
       export OPENAI_API_KEY="sk-..."
  2. Run:
       python3 llm_refine.py
  3. Manually review the suggestions or (with caution) rely on automatic patching.
"""

import os
import json
import openai   # pip install openai
import re

# Path to the analysis report from Step 5
ANALYSIS_REPORT = "test_artifacts/analysis_report.json"

# Example: Path to your main C code or the entire codebase to read from
TARGET_CODE_FILE = "../main.c"

# Choose your model (if you have GPT-4 access):
MODEL_NAME = "gpt-4"
# If you do not have GPT-4 access, you could use:
# MODEL_NAME = "text-davinci-003"

openai.api_key = "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"
if not openai.api_key:
    print("ERROR: No OpenAI API key found. Set OPENAI_API_KEY env var.")
    exit(1)

def load_analysis_report(report_path):
    """
    Load the vulnerabilities discovered in Step 5.
    Each item might have: file, line, keyword, threat, cwe, line_text
    """
    if not os.path.isfile(report_path):
        print(f"No analysis report found at: {report_path}")
        return []
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def read_code_snippet(filepath, line_num, context=5):
    """
    Reads 'context' lines before and after 'line_num' to give the LLM
    some surrounding code to see.
    """
    if not os.path.isfile(filepath):
        return None

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    start_line = max(0, line_num - context - 1)
    end_line = min(len(lines), line_num + context)
    snippet = lines[start_line:end_line]
    return snippet

def prompt_llm_for_fix(snippet, cwe_info, line_text):
    """
    Prompt GPT-4 (or Davinci) for a fix suggestion based on the snippet,
    referencing the discovered vulnerability (CWE, line_text, etc.).
    """
    prompt = f"""
You are a helpful AI that fixes security flaws in embedded C code.

We found the following vulnerability: {cwe_info}

Here is a snippet of the code around the vulnerable line:
------------------------------------------------------
{snippet}
------------------------------------------------------

The line triggering this vulnerability or error was: 
"{line_text}"

Please suggest a revised snippet or patch to fix or mitigate this issue, 
while preserving the original logic as much as possible.
Explain your changes briefly at the end.
"""

    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful C programming assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=700
    )

    fix_suggestion = response.choices[0].message.content
    return fix_suggestion

def extract_code_block(suggestion_text):
    """
    Naive approach:
     - Looks for a triple-backtick-enclosed code block in the LLM suggestion.
     - Returns just the code within the first triple-backtick block found.
     - If none found, returns None.
    """
    # Regex that captures text between the first pair of triple backticks
    match = re.search(r'```(.*?)```', suggestion_text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def apply_patch_to_file(file_path, old_snippet, new_snippet):
    """
    Another naive approach:
      1. Read entire file.
      2. Find the old snippet as a contiguous string. (If it’s not contiguous, this may fail.)
      3. Replace it with the new snippet.
      4. Overwrite the file with the new content.
    """

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        original_content = f.read()

    # We'll attempt a direct string replacement.
    # If the snippet doesn't match exactly, you may need a more robust approach:
    patched_content = original_content.replace("".join(old_snippet), new_snippet)

    # If no changes, maybe the LLM snippet was too different or didn't match:
    if patched_content == original_content:
        print("WARNING: Could not apply patch automatically "
              "(old snippet not found or mismatch).")
        return

    # Otherwise, write updated content to file
    backup_path = file_path + ".bak"
    with open(backup_path, "w", encoding="utf-8", errors="ignore") as backup_f:
        backup_f.write(original_content)
    print(f"Backup of original file created: {backup_path}")

    with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(patched_content)
    print(f"Patched file saved: {file_path}")

def main():
    vulnerabilities = load_analysis_report(ANALYSIS_REPORT)
    if not vulnerabilities:
        print("No vulnerabilities found in analysis_report.json. Nothing to refine.")
        return

    # Group vulnerabilities by file so we can read code from that file
    vulns_by_file = {}
    for v in vulnerabilities:
        fname = v["file"]
        if fname not in vulns_by_file:
            vulns_by_file[fname] = []
        vulns_by_file[fname].append(v)

    for fname, vulns in vulns_by_file.items():
        # Attempt to resolve the actual path to the code file
        if not os.path.isfile(fname):
            # If the file is "main.c" but in a different directory, try TARGET_CODE_FILE
            if fname == os.path.basename(TARGET_CODE_FILE):
                actual_path = TARGET_CODE_FILE
            else:
                print(f"Skipping {fname}, can't find actual path.")
                continue
        else:
            actual_path = fname

        print(f"\n=== Processing vulnerabilities in {actual_path} ===")

        # Sort vulnerabilities by line number for consistent reading
        sorted_vulns = sorted(vulns, key=lambda x: x["line"])

        for v in sorted_vulns:
            line_num = v["line"]
            snippet = read_code_snippet(actual_path, line_num, context=5)
            if snippet is None:
                print(f"Cannot read snippet from {actual_path}")
                continue

            # Build a short CWE + line_text descriptor
            cwe_info = f"{v['threat']} ({v['cwe']})"
            line_text = v['line_text']

            print(f"\nVulnerability at line {line_num}, keyword='{v['keyword']}' => {cwe_info}")
            suggestion = prompt_llm_for_fix("".join(snippet), cwe_info, line_text)
            print("\n--- LLM Fix Suggestion ---")
            print(suggestion)
            print("--- End of Suggestion ---\n")

            # OPTIONAL: Attempt to parse the LLM suggestion and auto-apply it:
            suggested_code = extract_code_block(suggestion)
            if suggested_code:
                print("Attempting to apply the following code patch to file:")
                print(suggested_code)
                apply_patch_to_file(actual_path, snippet, suggested_code)
            else:
                print("No clear code block found in the suggestion. Skipping auto-patch.")

if __name__ == "__main__":
    main()
