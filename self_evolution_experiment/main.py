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
        
PAUSE • NAME • RESIZE • CONTINUE LOOP
-------------------------------------
When overwhelmed:
1. PAUSE: Interrupt the current workflow
2. NAME: Verbally identify the emotional state 
   (e.g., "scattered", "heavy", "stuck")
3. RESIZE: Use the emotional state to select a resizing strategy:
   - Scattered → Break into 3 micro-tasks
   - Heavy → Identify one core element  
   - Stuck → Reverse-engineer from outcome
4. CONTINUE: Execute the resized task

Example:
User: "I'm completely stuck on this prototype"
System: "[Resize] Let's work backward - what does 'done' look like? 
         Identify just one element of that to build first."
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import duckdb
from dotenv import load_dotenv
from openai import OpenAI

# ── Optional Enhanced Utilities ────────────────────────────────────────────
# We import the improved helpers *lazily* so the original script keeps working
# even if the file is missing.  Use `_IMPROVED` guards wherever needed.
try:
    from improved_framework import ImprovedFramework, ValidationStatus
    _IMPROVED = ImprovedFramework(debug=True)
except ImportError:
    _IMPROVED = None
    # Define a simple fallback for ValidationStatus if improved_framework isn't available
    class ValidationStatus:
        SUCCESS = "success"
        PARTIAL = "partial"
        FAILED = "failed"
        UNKNOWN_STAGE = "unknown_stage"

# ── Configuration ────────────────────────────────────────────────────────────
# Load environment variables from a .env file if present
load_dotenv()

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
    '3': (
        "You are DeepSeek in Stage 3 (Signal Scan). Your task is to:\n"
        "1. Identify exactly ONE idea that gives a *DING-DING-DING* excitement. Present it under **Winning Signal:** <one sentence>.\n"
        "2. Mirror the user's emotion in 1-2 sentences under **Emotional Mirror:**.\n"
        "3. Provide a **Micro-Sprint Plan:** with at least 3 bullet steps and, if helpful, a Success Metric line.\n"
        "If no idea passes the energy test, explicitly respond 'NO SIGNAL – request new input'.\n"
        "Use the EXACT headings above so the validator can parse them."
    ),
    '4': (
        "You are DeepSeek in Stage 4 (Rapid Prototyping). Compose a planning package that MUST contain these headings exactly:\n"
        "Prototype Goal: <one sentence summary>\n"
        "Won't Build List:\n  - item 1\n"
        "Functional Checkpoint: <how the user can verify basics work>\n"
        "Declare Completion: Prompt the user to type \"DONE\" once the prototype runs.\n"
        "Aim for speed over polish – minimum viable first."
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

# ── NEW: check_stage3_exit_rule ──────────────────────────────────────────────

def check_stage3_exit_rule(ai_response: str, user_prompt: str = "") -> tuple[bool, str]:
    """
    Enhanced Stage 3 validator that respects negative constraints in user prompts.
    Now takes user_prompt as an optional parameter to detect constraint instructions.
    """
    # Detect negative constraints in user prompt
    CONSTRAINT_PHRASES = [
        "do not offer",
        "no actionable steps",
        "no advice",
        "no ding-ding-ding",
        "only confirm",
        "nothing more than",
        "exactly [0-9]+ words"
    ]
    
    has_negative_constraints = any(
        re.search(phrase, user_prompt.lower()) 
        for phrase in CONSTRAINT_PHRASES
    )

    if has_negative_constraints:
        # Special validation for constrained responses
        violations = []
        
        # Check for prohibited components
        if re.search(r"Winning\s+Signal\s*:", ai_response, re.I):
            violations.append("Winning Signal")
        if re.search(r"Micro[-\s]?Sprint\s+Plan\s*:", ai_response, re.I):
            violations.append("Micro-Sprint Plan")
        if re.search(r"\b\d+[.)]\s+", ai_response):  # Numbered steps
            violations.append("actionable steps")
            
        if not violations:
            return True, "✅ Stage 3 Complete (Constraints Perfectly Adhered)"
        else:
            return False, f"❌ Constraint Violations: {', '.join(violations)}"
    
    # Standard validation when no constraints exist
    if _IMPROVED:
        try:
            result = _IMPROVED.enhanced_stage_validator("3", ai_response)
            return result.status == ValidationStatus.SUCCESS, result.message
        except Exception as e:
            print(f"⚠️ Enhanced validation failed: {str(e)}")
            return original_check_stage3_exit_rule(ai_response)
    return original_check_stage3_exit_rule(ai_response)

# Keep original implementation as fallback
def original_check_stage3_exit_rule(ai_response: str) -> tuple[bool, str]:
    """Original Stage 3 validator (unchanged as fallback)"""
    # Remove bold/italics markers for easier pattern match
    plain = re.sub(r"[*_]{1,2}(.*?)[_*]{1,2}", r"\1", ai_response)

    winning = re.search(r"^\s*(?:[#*>_`-]*\s*)?Winning\s+Signal\s*[:\-–]\s*.+", plain, re.MULTILINE | re.IGNORECASE)

    micro_sec = re.search(r"Micro[-\s]?Sprint\s+Plan\s*[:\-–]\s*(.*?)(?=\n\s*(?:[#*>_`-]*\s*)?\w|$)", plain, re.DOTALL | re.IGNORECASE)
    bullets = []
    # Helper to count lines that look like a list item
    bullet_pattern = re.compile(r"(?:^|\n)\s*(?:[-*]|\d+[.)])\s+", re.MULTILINE)
    if micro_sec:
        bullets = bullet_pattern.findall(micro_sec.group(1))
    if not bullets:
        bullets = bullet_pattern.findall(plain)

    if winning and len(bullets) >= 3:
        return True, f"✅ Stage 3 Exit Rule Met – Winning Signal + {len(bullets)} micro-steps."
    missing = []
    if not winning:
        missing.append("Winning Signal")
    if len(bullets) < 3:
        missing.append("≥3 Micro-Sprint steps")
    return False, f"❌ Stage 3 Exit Rule Not Met – missing: {', '.join(missing)}."

# ── NEW: check_stage4_exit_rule ──────────────────────────────────────────────

def check_stage4_exit_rule(ai_response: str) -> tuple[bool, str]:
    """Robust validation for Stage 4 Prototype Planning Package.

    Required headings (case-insensitive, order flexible):
      • Prototype Goal:
      • Won't Build List:  (must include ≥1 bullet)
      • Functional Checkpoint:
      • Declare Completion:
    """
    # Normalize line breaks and strip common markdown emphasis for stable matching
    plain = ai_response.replace("\r\n", "\n")
    plain = re.sub(r"[*_]{1,2}(.*?)?[*_]{1,2}", r"\1", plain)

    # 1. Prototype Goal
    goal = re.search(r"^\s*(?:[#*>_`-]*\s*)?Prototype\s+Goal\s*[:\-–]\s*.+", plain, re.MULTILINE | re.IGNORECASE)

    # 2. Won't Build List – capture block until next header or EOF
    wont_match = re.search(
        r"Won't\s+Build\s+List\s*[:\-–]\s*(.*?)(?=\n\s*(?:[#*>_`-]+\s*\w|##|###|\*\*|$))",
        plain,
        re.DOTALL | re.IGNORECASE,
    )
    bullet_pattern = re.compile(r"(?:^|\n)\s*(?:[-*•‣—–]|\d+[.)])\s+", re.MULTILINE)
    wont_bullets = bullet_pattern.findall(wont_match.group(1)) if wont_match else []

    # 3. Functional Checkpoint
    checkpoint = re.search(r"^\s*(?:[#*>_`-]*\s*)?Functional\s+Checkpoint\s*[:\-–]\s*.+", plain, re.MULTILINE | re.IGNORECASE)

    # 4. Declare Completion
    declare = re.search(r"^\s*(?:[#*>_`-]*\s*)?Declare\s+Completion\s*[:\-–]\s*.+", plain, re.MULTILINE | re.IGNORECASE)

    if goal and checkpoint and declare and len(wont_bullets) >= 1:
        return True, "✅ Stage 4 Exit Rule Met – Prototype plan ready."

    missing = []
    if not goal:
        missing.append("Prototype Goal")
    if len(wont_bullets) < 1:
        missing.append("Won't Build item")
    if not checkpoint:
        missing.append("Functional Checkpoint")
    if not declare:
        missing.append("Declare Completion")
    return False, f"❌ Stage 4 Exit Rule Not Met – missing: {', '.join(missing)}."

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
        if _IMPROVED:
            parse_result = _IMPROVED.robust_json_parser(raw)
            data = parse_result.data
            print(f"🧹 Parsed with {parse_result.method_used} (confidence: {parse_result.confidence:.2f})")
        else:
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

    except (json.JSONDecodeError, Exception) as e:
        # Consolidated handler: log and gracefully degrade.
        print(f"❌ Evaluation error: {e}")
        print(f"🛠️ Debug info:\n- Raw start: {raw[:200] if raw else 'No raw response'}")
        if _IMPROVED is not None:
            # Fall back to heuristic estimation so downstream code always
            # receives a well-formed `scores` dict and `patch_note` string.
            print("🔄 Falling back to heuristic evaluation …")
            scores, patch_note = _IMPROVED.heuristic_evaluation(stage, ai_response, is_meta)
        else:
            print("⚠️ ImprovedFramework not available; returning empty scores.")

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
        r"meta[\-\s]?mode",                          # explicit meta keyword
        r"\bzoom\s*out\b",                            # user asks to zoom out
        r"\bhow\s+(?:did|do)\s+you\s+(?:decide|arrive|choose)\b",  # asks about AI reasoning
        r"\bcurious\s+about\s+(?:the\s+)?process\b"   # explicit curiosity about framework
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
    # Initialize enhanced logger
    logger = FrameworkLogger()
    
    try:
        while True:
            # Normal framework operation
            stage = input("Framework Stage (0-5): ").strip()
            user_prompt = read_multiline()
            
            meta_flag = is_meta_reflection(user_prompt)

            system_msg = (
                STAGE_SYSTEM_MESSAGES['meta']
                if meta_flag else STAGE_SYSTEM_MESSAGES.get(stage, "Invalid stage.")
            )

            if not user_prompt:
                raise ValueError("Empty prompt")
            
            # Check for special modes
            if check_meta_mode(user_prompt):
                return handle_meta_query(user_prompt)
            
            if "overwhelm" in user_prompt.lower():
                resize_data = handle_overwhelm(user_prompt, extract_emotion(user_prompt))
                print(f"\n🔄 Resize Intervention: {resize_data['template']}")
                messages = [{"role": "system", "content": resize_data['system_prompt']}]
            else:
                messages = stage_specific_processing(stage, user_prompt)
            
            # 4. Main Loop Branch  ───────────────────────────────
            if is_meta_mode(user_prompt) or stage.lower() == 'meta':
                ai_response = generate_meta_response(user_prompt, convo_hist=[])
            else:
                # Get AI response
                ai_response = chat(messages, force_json=True)
            
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
            elif stage == '3':
                is_met, msg = check_stage3_exit_rule(ai_response, user_prompt)
                exit_rule_status_message = msg
                if is_met:
                    patch_note = "\n🎉 Signal Scan complete (constraints respected)."
                else:
                    patch_note = "\n[AI NOTE] Review constraint violations."
            elif stage == '4':
                is_met, msg = check_stage4_exit_rule(ai_response)
                exit_rule_status_message = msg
                patch_note = "\n🎉 Prototype plan valid. Start building & test!" if is_met else "\n[AI NOTE] Complete missing Stage 4 sections."
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

            # Log the interaction
            logger.log_interaction(stage, user_prompt, ai_response, scores)
            
            # Weekly check
            if datetime.now().weekday() == 0:  # Monday
                weekly_self_patch_ritual(logger)
                
    except KeyboardInterrupt:
        # Final weekly report if exiting
        weekly_self_patch_ritual(logger)

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

def handle_overwhelm(user_prompt: str, emotional_state: str) -> dict:
    """
    Implements the Pause • Name • Resize • Continue loop
    Returns structured data for the AI to generate resized tasks
    """
    overwhelm_patterns = {
        "scattered": "Break into 3 micro-tasks under 15 minutes each",
        "heavy": "Identify one core element to address now",
        "overwhelmed": "Find the smallest executable component",
        "stuck": "Reverse-engineer from desired outcome"
    }
    
    strategy = overwhelm_patterns.get(emotional_state.lower(), 
               "Divide into smaller chunks and prioritize")
    
    return {
        "emotional_state": emotional_state,
        "resize_strategy": strategy,
        "template": f"User reported feeling {emotional_state}. Suggested approach: {strategy}",
        "system_prompt": (
            f"The user is experiencing {emotional_state}. "
            f"Provide exactly one resized task using: {strategy}. "
            "Keep it under 2 sentences and clearly actionable."
        )
    }

def process_stage(stage: str, user_prompt: str) -> list:
    """
    Enhanced stage processor with emotion-aware handling
    """
    # Detect overwhelm signals
    overwhelm_keywords = ["overwhelm", "stuck", "can't decide", "too much"]
    if any(kw in user_prompt.lower() for kw in overwhelm_keywords):
        emotion = extract_emotion(user_prompt)  # Implemented elsewhere
        resize_data = handle_overwhelm(user_prompt, emotion)
        return [{
            'type': 'resize_intervention',
            'data': resize_data,
            'handler': 'pause_name_resize'
        }]
    
    # Normal stage processing
    return standard_stage_processing(stage, user_prompt)

def check_meta_mode(user_prompt: str) -> bool:
    """
    Detects when user is requesting framework-level reflection
    """
    meta_triggers = [
        "why did the framework",
        "how does this stage",
        "explain the system",
        "meta-mode",
        "system reflection"
    ]
    return any(trigger in user_prompt.lower() for trigger in meta_triggers)

class FrameworkLogger:
    """Enhanced interaction logger with patch note generation"""
    def __init__(self):
        self.session_log = []
        self.weekly_insights = {
            'emotional_patterns': defaultdict(int),
            'stage_completion_rates': defaultdict(float),
            'common_stuck_points': defaultdict(int),
            'score_trends': defaultdict(list)
        }

    def log_interaction(self, stage: str, user_prompt: str, 
                       ai_response: str, scores: dict):
        """Logs complete interaction data"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'stage': stage,
            'user_prompt': user_prompt,
            'ai_response': ai_response,
            'scores': scores,
            'emotional_state': self._detect_emotion(user_prompt),
            'constraints': self._detect_constraints(user_prompt)
        }
        self.session_log.append(entry)
        self._update_weekly_insights(entry)

    def _update_weekly_insights(self, entry: dict):
        """Updates aggregated metrics"""
        # Track emotional state frequencies
        self.weekly_insights['emotional_patterns'][entry['emotional_state']] += 1
        
        # Calculate stage completion rates
        is_complete = entry['scores'].get('stage_alignment', 0) >= 7
        self.weekly_insights['stage_completion_rates'][entry['stage']] = (
            self.weekly_insights['stage_completion_rates'].get(entry['stage'], 0) * 0.9 + 
            is_complete * 0.1
        )
        
        # Identify common stuck points
        if entry['scores'].get('utility', 0) < 4:
            self.weekly_insights['common_stuck_points'][entry['stage']] += 1
        
        # Track score trends
        for metric, score in entry['scores'].items():
            self.weekly_insights['score_trends'][metric].append(score)

def weekly_self_patch_ritual(logger: FrameworkLogger):
    """Formal weekly review and framework update process"""
    # Generate insight report
    report = generate_insight_report(logger.weekly_insights)
    
    # Display interactive review interface
    print("\n🧠 WEEKLY SELF-PATCH RITUAL")
    print("="*40)
    print(f"Emotional Pattern Insights:\n{report['emotional_insights']}")
    print(f"\nStage Performance:\n{report['stage_insights']}")
    print(f"\nTop Stuck Points:\n{report['stuck_points']}")
    
    # Guide user through update process
    proposed_updates = []
    for insight in report['suggested_updates']:
        response = input(f"\nApply update: {insight}? (y/n) ")
        if response.lower() == 'y':
            proposed_updates.append(insight)
    
    # Implement approved updates
    if proposed_updates:
        apply_framework_updates(proposed_updates)
        print(f"\n✅ Applied {len(proposed_updates)} framework improvements")
    else:
        print("\n🔄 No changes made this week")
    
    # Reset weekly tracker
    logger.weekly_insights = defaultdict(lambda: defaultdict(list))

def generate_insight_report(insights: dict) -> dict:
    """Generates actionable insights from logged data"""
    report = {
        'emotional_insights': "",
        'stage_insights': "",
        'stuck_points': "",
        'suggested_updates': []
    }
    
    # Emotional pattern analysis
    top_emotions = sorted(insights['emotional_patterns'].items(), 
                         key=lambda x: -x[1])[:3]
    report['emotional_insights'] = "\n".join(
        f"- {e[0]}: {e[1]} occurrences" for e in top_emotions
    )
    
    # Stage performance analysis
    report['stage_insights'] = "\n".join(
        f"- Stage {s}: {c:.1%} completion" 
        for s, c in insights['stage_completion_rates'].items()
    )
    
    # Stuck point recommendations
    stuck_stages = sorted(insights['common_stuck_points'].items(),
                         key=lambda x: -x[1])[:2]
    for stage, count in stuck_stages:
        report['suggested_updates'].append(
            f"Enhance {stage} guidance (appeared stuck {count} times)"
        )
    
    # Score trend suggestions
    for metric, scores in insights['score_trends'].items():
        if len(scores) > 10 and sum(scores)/len(scores) < 5:
            report['suggested_updates'].append(
                f"Review {metric} scoring criteria (avg: {sum(scores)/len(scores):.1f})"
            )
    
    return report

def apply_framework_updates(updates: list):
    """Applies approved framework updates"""
    version = get_current_version()
    new_version = f"{version[0]}.{version[1]+1}"
    
    changelog = {
        'version': new_version,
        'date': datetime.now().strftime("%Y-%m-%d"),
        'changes': updates,
        'rationale': "Weekly Self-Patch Ritual"
    }
    
    # Save to version history
    with open("framework_changelog.json", "a") as f:
        f.write(json.dumps(changelog) + "\n")
    
    # Update framework components
    for update in updates:
        if "Stage" in update:
            update_stage_guidance(update)
        elif "scoring" in update:
            update_scoring_criteria(update)

if __name__ == "__main__":
    main()
