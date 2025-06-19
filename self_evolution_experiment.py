"""
Self‑Evolution Experiment Script – DeepSeek Edition v0.5
========================================================
• JSON parsing now uses both forced JSON mode AND markdown cleanup
• Added comprehensive debug logging for API responses
• Improved error recovery with detailed diagnostics
• Maintained all v0.4 hardening

Run ➜  pip install openai duckdb
        export DEEPSEEK_API_KEY=sk‑...
        python self_evolution_experiment.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import duckdb
from openai import OpenAI

# ── Configuration ────────────────────────────────────────────────────────────
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DB_PATH = Path("self_evo_logs.duckdb").resolve()

# ── Database Setup ───────────────────────────────────────────────────────────
RUBRIC = [
    ("clarity", "Is the answer clear and understandable?"),
    ("stage_alignment", "Does the answer match the declared framework stage?"),
    ("tone", "Does the tone match the user's emotional state?"),
    ("utility", "Does it help move the project forward?"),
    ("empathy", "Does the user feel seen and not overwhelmed?"),
]

def init_database():
    """Initialize database with error handling."""
    try:
        conn = duckdb.connect(str(DB_PATH))
        conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id UUID PRIMARY KEY,
            timestamp TIMESTAMP,
            stage VARCHAR,
            user_prompt TEXT,
            ai_response TEXT,
            self_scores JSON,
            patch_note TEXT
        );
        """)
        return conn
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise

CONN = init_database()

# ── LLM Communication ────────────────────────────────────────────────────────
def chat(messages: list[dict], *, force_json: bool = False) -> str:
    """Send request to DeepSeek with enhanced debugging."""
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        kwargs = {"response_format": {"type": "json_object"}} if force_json else {}
        
        print(f"🤖 Sending {'JSON-' if force_json else ''}request to {MODEL}...")
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            **kwargs
        )
        result = resp.choices[0].message.content.strip()
        print(f"✅ Received {len(result)} chars")
        return result
    except Exception as e:
        print(f"❌ API call failed: {type(e).__name__}: {e}")
        raise

# ── Self-Evaluation ──────────────────────────────────────────────────────────
def extract_json_response(raw: str) -> dict:
    """
    Robust JSON extractor with:
    1. Markdown fence removal
    2. JSON object extraction
    3. Multiple fallback strategies
    """
    strategies = [
        lambda s: json.loads(s),  # Try direct parse first
        lambda s: json.loads(re.sub(r'^```(json)?|```$', '', s, flags=re.MULTILINE).strip()),
        lambda s: json.loads(s[s.find('{'):s.rfind('}')+1])
    ]
    
    last_error = None
    for strategy in strategies:
        try:
            return strategy(raw)
        except (json.JSONDecodeError, ValueError, AttributeError) as e:
            last_error = e
            continue
    
    raise last_error or ValueError("No valid JSON found in response")

def self_eval(stage: str, user_prompt: str, ai_response: str) -> tuple[dict, str]:
    """Enhanced self-evaluation with robust parsing."""
    rubric_str = "\n".join(f"{i+1}. {k}: {v}" for i, (k,v) in enumerate(RUBRIC))
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are the Ideate‑to‑Create self‑critique module. "
                "Return ONLY a JSON object with this exact structure:\n"
                "{\"scores\":{\"clarity\":int,...,\"empathy\":int}, \"patch_note\":str}\n"
                "Do NOT include markdown fences or commentary."
            )
        },
        {
            "role": "user",
            "content": f"RUBRIC:\n{rubric_str}\n\nSTAGE:{stage}\nPROMPT:\n{user_prompt}\nRESPONSE:\n{ai_response}"
        }
    ]

    print("\n🔍 Starting self-evaluation with robust parsing...")
    try:
        raw = chat(messages, force_json=True)
        print(f"📊 Raw response start: {raw[:120]}...")
        
        data = extract_json_response(raw)
        print(f"🧹 Parsed JSON keys: {list(data.keys())}")
        
        # Validate structure
        if not all(k in data for k in ("scores", "patch_note")):
            raise ValueError("Missing required fields")
        if not all(k in data["scores"] for k,_ in RUBRIC):
            print("⚠️  Missing some rubric scores")
            
        return data["scores"], data["patch_note"]
        
    except Exception as e:
        print(f"❌ Evaluation failed: {type(e).__name__}: {e}")
        print(f"🛠️  Debug info:\n- Raw start: {raw[:200]}\n- Error: {e}")
        return {}, f"Evaluation error: {str(e)}"

def save_interaction(
    stage: str,
    user_prompt: str,
    ai_response: str,
    scores: dict,
    patch_note: str,
) -> None:
    """Save interaction to database."""
    CONN.execute(
        "INSERT INTO interactions VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            time.strftime("%Y-%m-%d %H:%M:%S"),
            stage,
            user_prompt,
            ai_response,
            json.dumps(scores, ensure_ascii=False),
            patch_note,
        ),
    )

# ── Main Execution ───────────────────────────────────────────────────────────
def main():
    """Enhanced main loop with better error handling."""
    print(f"🚀 Self-Evolution Experiment v0.5 | DB: {DB_PATH}")
    
    try:
        stage = input("Framework Stage (0‑5): ").strip()
        user_prompt = read_multiline()
        
        if not user_prompt:
            raise ValueError("Empty prompt")
            
        # Get AI response
        ai_response = chat([
            {"role": "system", "content": "You are a creative collaborator..."},
            {"role": "user", "content": user_prompt}
        ])
        
        print("\n" + "="*50)
        print("🤖 AI RESPONSE".center(50))
        print("="*50)
        print(ai_response)
        print("="*50)
        print(f"\n📝 Response length: {len(ai_response)} characters")
        print("="*50 + "\n")
        
        # Self-evaluation
        scores, note = self_eval(stage, user_prompt, ai_response)
        
        # Save results
        save_interaction(stage, user_prompt, ai_response, scores, note)
        print(f"\n✅ Session saved | Scores: {scores}")

    except Exception as e:
        print(f"\n❌ Fatal error: {type(e).__name__}: {e}")
        sys.exit(1)

def read_multiline(prompt: str = "Your prompt ➜ ") -> str:
    """Read multiline input until EOF marker."""
    print(prompt + "(finish with EOF on its own line)")
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "EOF":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines).strip()

if __name__ == "__main__":
    main()
