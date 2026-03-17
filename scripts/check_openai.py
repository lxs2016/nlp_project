"""Verify OpenAI API is reachable and .env is loaded. Run from project root: python scripts/check_openai.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print(f"[OK] Loaded .env from {env_path}")
    except ImportError as e:
        print(f"[WARN] Could not load .env: {e}")
        print("       Install: pip install python-dotenv   (or: pip install -r requirements.txt)")
    except Exception as e:
        print(f"[WARN] Could not load .env: {e}")
else:
    print(f"[WARN] No .env at {env_path}")

api_key = (
    os.environ.get("OPENROUTER_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("API_KEY")
)
model = os.environ.get("OPENROUTER_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
base_url = os.environ.get("OPENROUTER_API_BASE") or os.environ.get("OPENAI_API_BASE")
if not base_url and os.environ.get("OPENROUTER_API_KEY"):
    base_url = "https://openrouter.ai/api/v1"

if not api_key:
    print("[FAIL] OPENAI_API_KEY / OPENROUTER_API_KEY (or API_KEY) not set in environment.")
    print("       In .env use:  OPENAI_API_KEY=sk-...   or  OPENROUTER_API_KEY=sk-or-...")
    print("       For OpenRouter add:  OPENAI_API_BASE=https://openrouter.ai/api/v1")
    sys.exit(1)

print(f"[OK] API key is set (length={len(api_key)})")
print(f"[INFO] Model: {model}")
if base_url:
    print(f"[INFO] Base URL: {base_url} (OpenRouter)")

# Call API with minimal request (same as generator)
try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You reply with a single short line."},
            {"role": "user", "content": "Say hello in one sentence."},
        ],
        max_tokens=50,
    )
    if r.choices:
        content = (r.choices[0].message.content or "").strip()
        print(f"[OK] OpenAI response: {content[:200]}{'...' if len(content) > 200 else ''}")
    else:
        print("[WARN] No choices in response.")
except Exception as e:
    print(f"[FAIL] OpenAI call error: {e}")
    sys.exit(1)

# Optional: run generator's _call_llm once to confirm full path
print("\n--- Testing generator _call_llm (same as game step) ---")
try:
    from models.generator import _call_llm
    raw = _call_llm(
        system="You are a story narrator. Reply with JSON: {\"narration\": \"...\", \"choices\": [\"A\", \"B\"], \"state_updates\": {}}.",
        user="Player says: 开始. Current state: 石溪镇广场.",
    )
    if "你站在当前场景中" in raw and "OPENAI" not in str(raw):
        print("[WARN] Got fallback JSON (API may have failed or returned non-JSON). Raw prefix:", raw[:120])
    else:
        print(f"[OK] Generator _call_llm returned ({len(raw)} chars). Prefix: {raw[:150]}...")
except Exception as e:
    print(f"[FAIL] Generator test: {e}")
    sys.exit(1)

print("\n[OK] API (OpenAI/OpenRouter) is correctly configured and callable.")
