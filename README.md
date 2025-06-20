# Self-Evolution Experiment

🚀 AI-Powered Ideation Framework with DeepSeek Integration

![Project Banner](https://example.com/path/to/banner.png) *(Optional: Add visual later)*

## Features

- **Structured Ideation Framework**: 6-stage process (0-5) for refining ideas
- **DeepSeek AI Integration**: Leverages `deepseek-chat` or `deepseek-reasoner` models
- **Automatic Self-Evaluation**: Scores responses against 5 quality metrics
- **Persistent Logging**: Stores all interactions in DuckDB database
- **Robust JSON Handling**: Specialized parsing for AI responses

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install openai duckdb
   ```

2. **Set API key**:
   ```bash
   export DEEPSEEK_API_KEY='your-api-key-here'
   ```

3. **Run the experiment**:
   ```bash
   python self_evolution_experiment.py
   ```

## Framework Stages

| Stage | Focus Area | Key Activities | Exit Rules |
|-------|------------|----------------|------------|
| 0 | Context Seed | Establish project foundation | [Success Today + Primary Constraint](#stage-0-exit-rules) |
| 1 | Brain Dump | Raw idea generation | [≥3 Key Themes](#stage-1-exit-rules) |
| 2 | Mind-Trace | Uncover hidden logic | [≥2 Patterns + Core Motivation](#stage-2-exit-rules) |
| 3 | Signal Scan | Deep dive & synthesis | TBD |
| 4 | Prototyping | Build quick tests | TBD |
| 5 | Implementation | Execute best ideas | TBD |

## Exit Rules

### Stage 0: Context Seed
**To advance**: AI must restate:
1. `Success Today: <one-sentence goal>`
2. `Primary Constraint: <one-sentence limitation>`

**Format Flexibility**:
- Supports Markdown (`**Success Today:**`, `### Primary Constraint:`)
- Case-insensitive (`SUCCESS TODAY:`, `primary constraint:`)

**Example**:
```markdown
✅ Valid:
**Success Today:** Validate course outline
> Primary Constraint: Limited to 4 hours/week

❌ Invalid:
"The goal is to finish the outline" (implied)
```

### Stage 1: Brain Dump
**To advance**: AI must identify ≥3 themes under `Key Themes:`

**Valid Formats**:
```markdown
✅ Valid:
Key Themes:
1. **AI Education**
- Beginner onboarding
* Monetization

❌ Invalid:
Key Themes: Various ideas (no list)
```

**Technical Note**:
- Regex: `r"Key Themes:.*?(\n\s*[-\*\d].+)+"`

### Stage 2: Mind-Trace
**To advance**: AI must document:
1. **≥2 Patterns** with:
   - `Pattern 1: <name>`
   - `Evidence: <quotes/examples>`
   - `Confidence: High/Medium/Low`
2. **Core Motivation**: `Core Motivation: <one-sentence>`
3. **Emotional Shift**: `Emotional Shift: <from X to Y>`

**Example**:
```markdown
Pattern 1: Problem-Solving as Identity
Evidence: "I jump from teaching to building tools"
Confidence: High

Core Motivation: To systematize mastery
Emotional Shift: Scattered → Focused
```

**Technical Notes**:
- Regex ignores whitespace/Markdown: `r"^\s*Pattern\s*\d+\s*:\s*.+"`
- [See implementation](self_evolution_experiment.py#L201)

## Example Workflow

```plaintext
1. Select stage (e.g., 2 for Mind-Trace)
2. Enter prompt (end with EOF):
   "Why did I jump from X to Y?"
3. Receive AI analysis with patterns/motivation
4. Automatic evaluation → "✅ Stage 2 Exit Rule Met"
5. Results logged to database
```

## Database Schema

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | TEXT | Interaction time |
| `stage` | INT | 0-5 |
| `exit_rule_met` | BOOL | True/False |
| `scores` | JSON | Clarity, alignment, etc. |

## Customization

Configure in script:
```python
# Model Selection
MODEL = "deepseek-chat"  # Alternatives: "deepseek-reasoner"

# Evaluation Rubric
RUBRIC = [
    ("clarity", "Is the response clear?"),
    ...
]
```

## Troubleshooting

**Common Issues**:
- `API key not set`: Ensure DEEPSEEK_API_KEY is exported
- `JSON parse errors`: Check the debug output
- `Database issues`: Verify write permissions

## Roadmap

- [x] Stage 0-2 exit rules
- [ ] Stage 3-5 exit rules
- [ ] Web interface
- [ ] Team collaboration

## License

MIT License - Free for personal/commercial use