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

# Path to main.c (adjust if located elsewhere)
MAIN_C_PATH = "../main.c"


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
    where 'file' is now expected to be a FULL PATH.
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
    Optionally reads the entire main.c file for broader context, then
    appends that to the LLM prompt.
    """
    main_c_content = ""
    if os.path.isfile(MAIN_C_PATH):
        # Read the entire main.c for reference (you can limit how many lines you add if needed).
        with open(MAIN_C_PATH, "r", encoding="utf-8", errors="ignore") as mf:
            main_c_content = mf.read()

    # Conditionally add main.c content to the prompt.
    # If main.c is large, consider limiting how many lines you include here.
    if main_c_content:
        additional_context = f"\n\nAdditionally, here is the content of 'main.c' for context:\n{main_c_content}\n"
    else:
        additional_context = ""

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
 """ + additional_context

    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful C programming assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=700
    )

    return response.choices[0].message.content

def extract_code_block(suggestion_text):
    """
    Naive approach:
     - Looks for a triple-backtick-enclosed code block in the LLM suggestion.
     - Returns just the code within the first triple-backtick block found.
     - If none found, returns None.
    """
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

    patched_content = original_content.replace("".join(old_snippet), new_snippet)

    if patched_content == original_content:
        print("WARNING: Could not apply patch automatically "
              "(old snippet not found or mismatch).")
        return

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
        file_full_path = v["file"]  # Expecting absolute or full relative path
        if file_full_path not in vulns_by_file:
            vulns_by_file[file_full_path] = []
        vulns_by_file[file_full_path].append(v)

    for full_path, vulns in vulns_by_file.items():
        if not os.path.isfile(full_path):
            print(f"Skipping {full_path}, can't find actual path in filesystem.")
            continue

        print(f"\n=== Processing vulnerabilities in {full_path} ===")

        sorted_vulns = sorted(vulns, key=lambda x: x["line"])
        for v in sorted_vulns:
            line_num = v["line"]
            snippet = read_code_snippet(full_path, line_num, context=5)
            if snippet is None:
                print(f"Cannot read snippet from {full_path}")
                continue

            cwe_info = f"{v['threat']} ({v['cwe']})"
            line_text = v['line_text']

            print(f"\nVulnerability at line {line_num}, keyword='{v['keyword']}' => {cwe_info}")
            suggestion = prompt_llm_for_fix("".join(snippet), cwe_info, line_text)
            print("\n--- LLM Fix Suggestion ---")
            print(suggestion)
            print("--- End of Suggestion ---\n")

            suggested_code = extract_code_block(suggestion)
            if suggested_code:
                print("Attempting to apply the following code patch to file:")
                print(suggested_code)
                apply_patch_to_file(full_path, snippet, suggested_code)
            else:
                print("No clear code block found in the suggestion. Skipping auto-patch.")

if __name__ == "__main__":
    main()
