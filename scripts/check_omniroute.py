"""Verify that Nexus can reach an OpenAI-compatible OmniRoute gateway.

Run from the repository root:
    python scripts/check_omniroute.py

This sends one tiny real chat request; it never prints the API key.
"""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

base_url = os.getenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1").rstrip("/")
api_key = os.getenv("OMNIROUTE_API_KEY", "sk_omniroute")
model = os.getenv("NEXUS_OMNIROUTE_MODEL", "auto")

print("Nexus → OmniRoute connection check")
print(f"Endpoint: {base_url}")
print(f"Model:    {model}")
print("API key:  configured (value hidden)" if api_key else "API key:  MISSING")

if not api_key:
    print("\nFAIL: Set OMNIROUTE_API_KEY in your environment or .env file.")
    sys.exit(2)

try:
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=20.0, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Reply briefly and plainly."},
            {"role": "user", "content": "Reply with exactly: OmniRoute connected"},
        ],
        max_tokens=24,
    )
    answer = response.choices[0].message.content or ""
    if not answer.strip():
        raise RuntimeError("The gateway returned an empty response.")
    print("\nPASS: Nexus reached OmniRoute and received a chat completion.")
    print(f"Reply: {answer.strip()[:300]}")
except Exception as exc:
    print(f"\nFAIL: {type(exc).__name__}: {str(exc)[:500]}")
    print("\nCheck that OmniRoute is running, its API endpoint is reachable,")
    print("the API key is correct, and the selected model/provider is enabled.")
    if "127.0.0.1" in base_url or "localhost" in base_url:
        print("Note: localhost works only when Nexus and OmniRoute share a machine/network namespace.")
    sys.exit(1)
