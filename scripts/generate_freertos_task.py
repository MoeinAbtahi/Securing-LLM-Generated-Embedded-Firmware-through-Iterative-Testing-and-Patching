#!/usr/bin/env python3

"""
Step 2: LLM-Driven Code Generation using OpenAI API v0.28

Make sure you have installed:
   pip install openai==0.28.0

Usage:
   1. Run this script:
         python3 generate_freertos_task.py
   2. Copy/paste the LLM-generated code into your FreeRTOS project 
      (e.g., SecureNetworkTask.c), then integrate it into main.c 
      (xTaskCreate(...)) as needed.
"""

import openai

# Set your OpenAI API key here
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY

# This is a minimal snippet of your threat model to guide the LLM.
THREAT_MODEL_SNIPPET = """
We have identified the following threats:
1) Buffer Overflows
2) Race Conditions
3) Denial of Service
4) Unauthorized Access
We want a FreeRTOS-based network parsing task that mitigates buffer overflow 
via boundary checks, logs suspicious inputs, and uses minimal blocking calls 
to avoid DoS. The code should be in C.
"""

PROMPT_TEMPLATE = f"""
{THREAT_MODEL_SNIPPET}

Your task: Generate a C function named 'vSecureNetworkTask' for FreeRTOS on 
a Cortex-M environment that receives data from a simulated network driver, 
ensures boundary checks, and demonstrates basic concurrency protection 
if needed. Show all relevant #includes. The function should be compilable 
as part of a standard FreeRTOS project.
"""

def generate_secure_network_task():
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert in embedded C programming and FreeRTOS."},
            {"role": "user", "content": PROMPT_TEMPLATE}
        ],
        max_tokens=500,
        temperature=0.0,
    )
    return response["choices"][0]["message"]["content"].strip()

def main():
    generated_code = generate_secure_network_task()
    print("=== LLM-Generated Secure Network Task ===\n")
    print(generated_code)
    print("\n=== End of Generated Code ===")

if __name__ == "__main__":
    main()
