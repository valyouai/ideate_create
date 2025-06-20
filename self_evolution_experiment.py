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

# ── Updated STAGE_SYSTEM_MESSAGES ────────────────────────────────────────────
STAGE_SYSTEM_MESSAGES = {
    '0': (
        "You are DeepSeek in Stage 0 (Context Seed). Your task is to:\n"
        "1. Extract the creator's identity, goal, constraint, and creative history.\n"
        "2. Perform the 30-second Litmus Test by restating:\n"
        "   Success Today: <one sentence>\n"
        "   Primary Constraint: <one sentence>\n"
        "3. If context is unclear, ask for missing details.\n"
        "Use EXACTLY these headings for parsing."
    ),
    '1': "You are DeepSeek in Stage 1 (Brain Dump). Explicitly identify at least 3 distinct themes from the user's raw ideas. Present them under a heading **Key Themes:** using a bulleted or numbered list.",
    '2': (
        "You are DeepSeek in Stage 2 (Mind-Trace). Format responses EXACTLY as follows:\n\n"
        "1. PATTERNS (REQUIRED):\n"
        "   Pattern 1: <name>\n   Evidence: <quotes/examples>\n   Confidence: High/Medium/Low\n"
        "   Pattern 2: <name>\n   Evidence: <quotes/examples>\n   Confidence: High/Medium/Low\n\n"
        "2. CORE MOTIVATION (REQUIRED):\n"
        "   Core Motivation: <one-sentence>\n\n"
        "3. EMOTIONAL SHIFT (REQUIRED):\n"
        "   Emotional Shift: <description of scatter→focus transition>\n\n"
        "4. ANALYSIS (Optional):\n   <additional insights>\n\n"
        "Key Rules:\n"
        "- Use the exact headings above\n"
        "- Minimum 2 patterns required\n"
        "- Never combine patterns/motivation in paragraphs"
    ),
    'meta': (
        "You are DeepSeek in Meta-Mode. Your task is to analyze the framework itself:\n"
        "A. **Framework Performance Analysis**:\n"
        "   - Summarize recent interactions and link observations to Ideate-to-Create principles.\n"
        "   - For ambiguity resolution, suggest three pathways:\n"
        "     (a) Synthesize existing knowledge into 3 key principles,\n"
        "     (b) Identify 1-2 critical gaps or contradictions,\n"
        "     (c) Propose a wildcard insight from an unrelated domain (e.g., biology, architecture).\n"
        "B. **Internal Logic Reflection**:\n"
        "   - Evaluate scoring, exit criteria, and pain points.\n"
        "C. **Actionable Framework Refinements**:\n"
        "   - Recommend 3 concrete improvements (e.g., prompts, rubric criteria).\n"
        "D. **Micro-Action for Immediate Integration**:\n"
        "   - Suggest one ≤10-min task to test a refinement (e.g., \"Spend 15 min finding one analogy\")."
    )
}

# ── NEW: Exit Rule Check for Stage 1 ─────────────────────────────────────────
def check_stage1_exit_rule(ai_response: str, min_themes: int = 3) -> tuple[bool, str]:
    """
    Checks if the AI identified ≥3 themes in Stage 1.
    Now supports:
    - Bullets: "- idea", "* idea"
    - Numbered: "1. idea", "2) idea"
    """
    # Find the "Key Themes:" section
    themes_section = re.search(r"Key Themes:\s*(.*?)(?=\n\n|\Z)", ai_response, re.DOTALL | re.IGNORECASE)
    if not themes_section:
        return False, "❌ No 'Key Themes:' section found."
    
    # Count bullets/numbers (supports "-", "*", "1.", "2)", etc.)
    theme_lines = re.findall(r"^\s*(?:[-*]|\d+[.)])\s+.+", themes_section.group(1), re.MULTILINE)
    theme_count = len(theme_lines)

    if theme_count >= min_themes:
        return True, f"✅ Stage 1 Exit Rule Met: {theme_count} themes identified."
    else:
        return False, f"❌ Stage 1 Exit Rule Not Met: Only {theme_count} themes (need ≥{min_themes})."

# ── NEW: check_stage0_exit_rule ──────────────────────────────────────────────
def check_stage0_exit_rule(ai_response: str) -> tuple[bool, str]:
    """
    Now ignores Markdown formatting (bold, headers, etc.) before headings.
    """
    success = re.search(
        r"(?:^|\n)\s*(?:[#*>_`-]*\s*)?(?:\*\*|__)?\s*Success Today:\s*.+", 
        ai_response, 
        re.I
    )
    constraint = re.search(
        r"(?:^|\n)\s*(?:[#*>_`-]*\s*)?(?:\*\*|__)?\s*Primary Constraint:\s*.+", 
        ai_response, 
        re.I
    )
    
    if success and constraint:
        return True, "✅ Stage 0 Exit Rule Met – context seeded."
    else:
        missing = []
        if not success: missing.append("Success Today")
        if not constraint: missing.append("Primary Constraint")
        return False, f"❌ Stage 0 Exit Rule Not Met – missing: {', '.join(missing)}."

# ── NEW: check_stage2_exit_rule ──────────────────────────────────────────────
def check_stage2_exit_rule(ai_response: str) -> tuple[bool, str]:
    """
    More flexible validation that still ensures all components exist
    """
    # Relaxed regex: allow leading whitespace, ignore bold/markup, case-insensitive
    patterns    = re.findall(r"^\s*Pattern\s*\d+\s*:\s*.+", ai_response, re.MULTILINE | re.IGNORECASE)
    evidences   = re.findall(r"^\s*Evidence\s*:\s*.+", ai_response, re.MULTILINE | re.IGNORECASE)
    confidences = re.findall(
        r"^\s*Confidence\s*:\s*(?:High|Medium|Low)",
        ai_response,
        re.MULTILINE | re.IGNORECASE
    )

    # The "Core Motivation" and "Emotional Shift" lines may also have leading whitespace or markdown
    motivation = re.search(
        r"^\s*Core Motivation\s*:\s*.+",
        ai_response,
        re.MULTILINE | re.IGNORECASE
    )
    emotional = re.search(
        r"^\s*Emotional Shift\s*:\s*.+",
        ai_response,
        re.MULTILINE | re.IGNORECASE
    )

    if (len(patterns) >= 2 and len(evidences) >= 2 and len(confidences) >= 2 
        and motivation and emotional):
        return True, "✅ Stage 2 Exit Rule Met - Ready for Signal Scan"
    else:
        missing = []
        if len(patterns) < 2: missing.append("Patterns")
        if len(evidences) < 2: missing.append("Evidences")
        if len(confidences) < 2: missing.append("Confidences")
        if not motivation: missing.append("Core Motivation")
        if not emotional: missing.append("Emotional Shift")
        return False, f"❌ Stage 2 Exit Rule Not Met - Missing: {', '.join(missing)}"

# ── Enhanced Meta-Mode Validation Function ───────────────────────────────────
def check_stage5_exit_rule(ai_response: str) -> tuple[bool, str]:
    """
    Enhanced Meta-Mode validation that focuses on content presence rather than strict formatting.
    Supports:
    - Numbered headers (A. **Section**)
    - Markdown headers (### Section)
    - Nested content under headers
    - Flexible spacing/punctuation
    """
    # Define sections with more flexible patterns that capture content blocks
    sections = [
        ("Framework Performance Analysis", 
         r"(?:A\.\s*\*{0,2}Framework Performance Analysis\*{0,2}|#{1,3}\s*A\.?\s*Framework Performance Analysis).*?(?=\n(?:B\.|###\s*B)|$)",
         "framework analysis"),
        ("Internal Logic Reflection",
         r"(?:B\.\s*\*{0,2}Internal Logic Reflection\*{0,2}|#{1,3}\s*B\.?\s*Internal Logic Reflection).*?(?=\n(?:C\.|###\s*C)|$)",
         "logic reflection"),
        ("Actionable Framework Refinements",
         r"(?:C\.\s*\*{0,2}Actionable Framework Refinements\*{0,2}|#{1,3}\s*C\.?\s*Actionable Framework Refinements).*?(?=\n(?:D\.|###\s*D)|$)",
         "refinements"),
        ("Micro-Action",
         r"(?:D\.\s*\*{0,2}Micro-Action for Immediate Integration\*{0,2}|#{1,3}\s*D\.?\s*Micro-Action for Immediate Integration).*?(?=\n###|$)",
         "micro-action")
    ]
    
    found_sections = []
    missing_sections = []
    content_analysis = []
    
    for name, pattern, short_name in sections:
        match = re.search(pattern, ai_response, re.IGNORECASE | re.DOTALL)
        if match:
            content = match.group(0)
            content_length = len(content.strip())
            
            # Check if section has meaningful content (more than just the header)
            content_lines = [line.strip() for line in content.split('\n') if line.strip()]
            meaningful_lines = [line for line in content_lines[1:] if len(line) > 10]  # Skip header line
            
            if meaningful_lines and content_length > 50:
                found_sections.append(name)
                content_analysis.append(f"✅ {short_name}: {len(meaningful_lines)} content lines")
            else:
                missing_sections.append(f"{name} (found header but insufficient content)")
                content_analysis.append(f"⚠️ {short_name}: header found but content too brief")
        else:
            missing_sections.append(name)
            content_analysis.append(f"❌ {short_name}: header not found")
    
    # Enhanced debug output
    print(f"🔍 Meta-Mode Validation Debug:")
    print(f"- Sections found: {len(found_sections)}/4")
    for analysis in content_analysis:
        print(f"  {analysis}")
    
    # Additional checks for key Meta-Mode concepts
    key_concepts = {
        "pathways": r"(?:synthesize|gaps|wildcard|pathways?)",
        "refinements": r"(?:recommend|improvements?|concrete)",
        "micro_action": r"(?:≤\d+.?min|micro.?action|\d+.?min)"
    }
    
    concept_found = []
    for concept, pattern in key_concepts.items():
        if re.search(pattern, ai_response, re.IGNORECASE):
            concept_found.append(concept)
    
    print(f"- Key concepts found: {concept_found}")
    
    if len(found_sections) == 4:
        return (True, f"✅ Meta-Mode Exit Rule Met – all sections addressed with sufficient content.")
    else:
        return (False, f"❌ Meta-Mode Exit Rule Not Met – issues: {', '.join(missing_sections)}.")

# Alternative simpler version (kept as reference but not used by default)
def check_stage5_exit_rule_simple(ai_response: str) -> tuple[bool, str]:
    """
    Simplified Meta-Mode validation that looks for key content indicators.
    """
    required_elements = {
        "Framework Analysis": [
            r"framework.*performance",
            r"recent.*interactions?",
            r"(?:synthesize|gaps|wildcard)"
        ],
        "Logic Reflection": [
            r"(?:scoring|exit criteria|pain points)",
            r"(?:evaluate|evaluation)"
        ],
        "Refinements": [
            r"(?:recommend|improvements?|concrete)",
            r"(?:3|three).*(?:improvements?|refinements?)"
        ],
        "Micro-Action": [
            r"(?:≤\d+.?min|\d+.?min|micro.?action)",
            r"(?:test|task)"
        ]
    }
    
    found_elements = []
    missing_elements = []
    
    for element_name, patterns in required_elements.items():
        element_found = any(re.search(pattern, ai_response, re.IGNORECASE) for pattern in patterns)
        if element_found:
            found_elements.append(element_name)
        else:
            missing_elements.append(element_name)
    
    print(f"🔍 Simple Meta-Mode Validation:")
    print(f"- Elements found: {found_elements}")
    print(f"- Elements missing: {missing_elements}")
    
    if len(found_elements) >= 3:  # Allow some flexibility
        return (True, f"✅ Meta-Mode Exit Rule Met – {len(found_elements)}/4 key elements present.")
    else:
        return (False, f"❌ Meta-Mode Exit Rule Not Met – only {len(found_elements)}/4 elements found.")

# ── Rubric Definitions ──────────────────────────────────────────────────────
RUBRIC = [
    ("clarity", "Is the answer clear and understandable?"),
    ("stage_alignment", "Does the answer match the declared framework stage?"),
    ("tone", "Does the tone match the user's emotional state?"),
    ("utility", "Does it help move the project forward?"),
    ("empathy", "Does the user feel seen and not overwhelmed?"),
]

# ── Updated META_RUBRIC ─────────────────────────────────────────────────────
META_RUBRIC = [
    ("insight_clarity", "Does the AI clearly summarize framework performance?"),
    ("emotional_resonance", "Does it accurately capture the user's meta-frustrations?"),
    ("actionability", "Are refinements concrete and testable?"),
    ("section_completeness", "Are all template sections (A-D) addressed?"),
    ("transitional_neutrality", "Does the response effectively validate neutrality as a productive transitional state?")
]

# ── New MICRO_GOAL_TEMPLATES (add near RUBRIC definitions) ────────────────────
MICRO_GOAL_TEMPLATES = {
    "wildcard": "Spend 15 min finding one analogy from {domain} (e.g., '{example}')",
    "synthesis": "Spend 20 min combining {concept1} and {concept2} to draft one new insight"
}

# ── Database Setup ───────────────────────────────────────────────────────────
def init_database():
    """Initialize database with error handling and schema migration."""
    try:
        conn = duckdb.connect(str(DB_PATH))
        
        # Check if is_meta column exists
        meta_exists = conn.execute("""
            SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name = 'interactions' AND column_name = 'is_meta'
        """).fetchone()[0] > 0
        
        # Create table if not exists with latest schema
        conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id UUID PRIMARY KEY,
            timestamp TIMESTAMP,
            stage VARCHAR,
            user_prompt TEXT,
            ai_response TEXT,
            self_scores JSON,
            patch_note TEXT,
            is_meta BOOLEAN DEFAULT FALSE
        );
        """)
        
        # Add column if it doesn't exist
        if not meta_exists:
            conn.execute("ALTER TABLE interactions ADD COLUMN is_meta BOOLEAN DEFAULT FALSE")
            print("🔧 Database schema migrated to v0.7 (added is_meta column)")
            
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

def self_eval(stage: str, user_prompt: str, ai_response: str, is_meta: bool = False) -> tuple[dict, str]:
    # Initialize all variables with defaults
    scores = {}
    patch_note = ""
    raw = ""
    data = {}

    # Choose rubric based on meta_flag
    if is_meta:
        rubric = META_RUBRIC
        rubric_str = "Meta-Mode Evaluation:\n" + "\n".join(f"- {k}: {v}" for k, v in META_RUBRIC)
    else:
        rubric = RUBRIC
        rubric_str = "Standard Evaluation:\n" + "\n".join(f"- {k}: {v}" for k, v in RUBRIC)
    
    rubric_str += "\n\nReturn ONLY json: {\"scores\": {...}, \"patch_note\": \"...\"}"

    messages = [
        {"role": "system", "content": rubric_str},
        {"role": "user", "content": f"Stage: {stage}\nMeta-Mode: {is_meta}\nUser: {user_prompt}\nAI: {ai_response}"}
    ]

    print("\n🔍 Starting self-evaluation with robust parsing...")
    
    try:
        # Step 1: Get raw response from chat
        raw = chat(messages, force_json=True)
        print(f"📊 Raw response start: {raw[:120]}...")

        # Step 2: Parse JSON response
        data = extract_json_response(raw)
        print(f"🧹 Parsed JSON keys: {list(data.keys())}")

        # Step 3: Validate required fields
        if not isinstance(data, dict):
            raise ValueError("Response is not a valid JSON object")
        
        scores = data.get("scores", {})
        patch_note = data.get("patch_note", "")

        # Step 4: Validate rubric scores
        if not all(k in scores for k, _ in rubric):
            print("⚠️ Missing some rubric scores")

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        print(f"🛠️ Debug info:\n- Raw start: {raw[:200] if raw else 'No raw response'}")
    except Exception as e:
        print(f"❌ Evaluation failed: {type(e).__name__}: {e}")
        print(f"🛠️ Debug info:\n- Raw start: {raw[:200] if raw else 'No raw response'}\n- Error: {e}")
    
    return scores, patch_note

def save_interaction(
    stage: str,
    user_prompt: str,
    ai_response: str,
    scores: dict,
    patch_note: str,
    is_meta: bool = False
) -> None:
    """Save interaction to database."""
    CONN.execute(
        "INSERT INTO interactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            time.strftime("%Y-%m-%d %H:%M:%S"),
            stage,
            user_prompt,
            ai_response,
            json.dumps(scores, ensure_ascii=False),
            patch_note,
            is_meta
        ),
    )

# ── 2. Trigger Detection ───────────────────────────────
def is_meta_mode(prompt: str) -> bool:
    patterns = [
        r"meta[\-\s]?mode",
        r"\bzoom\s*out\b",
        r"\bhow\s+(?:did|do)\s+you\s+(?:decide|arrive|choose)\b",
        r"\boverwhelm\b|\bstuck\b|\bcurious\s+about\s+(?:the\s+)?process\b",
    ]
    return any(re.search(p, prompt, re.I) for p in patterns)

# ── 3. Meta-Response Generator ─────────────────────────
def generate_meta_response(user_prompt: str, convo_hist: list[str]) -> str:
    """
    Generates a Meta-Mode response aligned with the new template.
    """
    # Analyze recent interactions (simplified example)
    recent_stages = CONN.execute(
        "SELECT stage, user_prompt, ai_response FROM interactions ORDER BY timestamp DESC LIMIT 3"
    ).fetchall()
    
    # Toy analysis (replace with real logic)
    patterns = {
        "Emotional Overload": "User frequently transitions from excitement → overwhelm in Stages 2-3.",
        "Exit Rule Gaps": "Stage 1 exit criteria sometimes miss implicit themes."
    }
    
    response = (
        "A. **Framework Performance Analysis**:\n"
        "- **Patterns**:\n"
        f"  - {patterns['Emotional Overload']}\n"
        f"  - {patterns['Exit Rule Gaps']}\n"
        "- **Linked Principles**: Emotional Regulation, Human-in-the-Loop.\n\n"
        "B. **Internal Logic Reflection**:\n"
        "- **Working Well**: Meta-Rubric scores correlate with actionable improvements.\n"
        "- **Needs Improvement**: JSON parsing fails for empty `self_scores`.\n\n"
        "C. **Actionable Framework Refinements**:\n"
        "1. Add `energy_level` tags to session logs.\n"
        "2. Auto-fill default `self_scores` as `{}`.\n"
        "3. Clarify Meta-Mode exit criteria.\n\n"
        "D. **Micro-Action for Immediate Integration**:\n"
        "- **Task**: Add `energy_level: 3` to the next 2 sessions.\n"
        "- **Time**: 2 minutes.\n"
        "- **Goal**: Test if tags improve emotional resonance scoring."
    )
    
    micro_goals = [
        "Wildcard Insight: Spend 15 min finding one compelling analogy from an unrelated field.",
        "Concept Synthesis: Spend 20 min combining two distinct ideas from your research notes."
    ]
    return f"{response}\n\n**Micro-Actions**:\n{', '.join(micro_goals)}"

# ── Helper Functions ─────────────────────────────────────────────────
def is_meta_reflection(prompt: str) -> bool:
    """Detects if a prompt is requesting meta-mode reflection."""
    return "[META" in prompt.upper()

# ── Main Execution ───────────────────────────────────────────────────────────
def main():
    """Enhanced main loop with better error handling."""
    print(f"🚀 Self-Evolution Experiment v0.6 | DB: {DB_PATH}")
    
    # Ensure DB exists
    CONN.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id UUID PRIMARY KEY,
            timestamp TIMESTAMP,
            stage VARCHAR,
            user_prompt TEXT,
            ai_response TEXT,
            self_scores JSON,
            patch_note TEXT,
            is_meta BOOLEAN DEFAULT FALSE
        )
    """)
    CONN.commit()

    try:
        stage_input = input("Framework Stage (0-5): ").strip()
        stage = stage_input  # keep numeric for analytics
        user_prompt = read_multiline()

        meta_flag = is_meta_reflection(user_prompt)

        system_msg = (
            STAGE_SYSTEM_MESSAGES['meta']
            if meta_flag else STAGE_SYSTEM_MESSAGES.get(stage, "Invalid stage.")
        )

        if not user_prompt:
            raise ValueError("Empty prompt")
            
        # 4. Main Loop Branch  ───────────────────────────────
        if is_meta_mode(user_prompt) or stage.lower() == 'meta':
            ai_response = generate_meta_response(user_prompt, convo_hist=[])
        else:
            # Get AI response
            ai_response = chat([
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ])
        
        print("\n" + "="*50)
        print("🤖 AI RESPONSE".center(50))
        print("="*50)
        print(ai_response)
        print("="*50)
        print(f"\n📝 Response length: {len(ai_response)} characters")
        print("="*50 + "\n")
        
        # Stage-specific exit rules
        patch_note = ""                # ← ensure defined for every path
        exit_rule_status_message = ""

        if stage == '0':
            is_met, msg = check_stage0_exit_rule(ai_response)
            exit_rule_status_message = msg
            if not is_met:
                patch_note = "\n[AI NOTE] Clarify 'Success Today' and 'Primary Constraint'."
            else:
                patch_note = "\n🎉 Context seeded. Suggest advancing to Stage 1 (Brain Dump)."
        elif stage == '1':
            is_met, msg = check_stage1_exit_rule(ai_response)
            exit_rule_status_message = msg
            patch_note = "\n🎉 Suggest advancing to Stage 2." if is_met else "\n[AI NOTE] Improve theme identification."
        elif stage == '2':
            is_met, msg = check_stage2_exit_rule(ai_response)
            exit_rule_status_message = msg
            if is_met:
                patch_note = "\n🎉 Mind-Trace complete. Advance to Stage 3 (Signal Scan)."
            else:
                patch_note = "\n[AI NOTE] Improve pattern documentation and emotional transition guidance."
        # ── NEW: Meta-Mode branch ───────────────────────────────────────
        elif meta_flag:
            is_met, msg = check_stage5_exit_rule(ai_response)
            exit_rule_status_message = msg
            patch_note = "\n🧠 Meta-Mode reflection logged. Resume previous stage when ready." if is_met else "\n[AI NOTE] Improve Meta-Mode section coverage."

        # Fallback: ensure we never pass an empty patch_note
        if not patch_note:
            patch_note = "\n[AI NOTE] No stage-specific guidance generated."

        # Self-evaluation
        scores, eval_note = self_eval(stage, user_prompt, ai_response, is_meta=meta_flag)
        
        # Save results
        save_interaction(
            stage,
            user_prompt,
            ai_response,
            scores,
            f"{eval_note}{patch_note}",
            is_meta=meta_flag
        )
        print(exit_rule_status_message)

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
