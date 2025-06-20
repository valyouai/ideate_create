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
| 2 | Pattern Recognition | Identify trends | [≥2 Validated Patterns](#stage-2-exit-rules) |
| 3 | Signal Scan | Deep dive & synthesis | TBD |
| 4 | Prototyping | Build quick tests | TBD |
| 5 | Implementation | Execute best ideas | TBD |

## Exit Rules

### Stage 0 Exit Rules
**To advance**: AI must explicitly restate:
1. `Success Today: <one-sentence goal>`
2. `Primary Constraint: <one-sentence limitation>`

**Format Examples**:
```markdown
✅ Valid:
**Success Today:** Ship a Figma prototype
### Primary Constraint: No coding skills

❌ Invalid:
"The goal is to build a prototype" (implied)
```

**Technical Details**:
- Regex ignores Markdown formatting: `r"\bSuccess Today:\s*.+"`
- [See implementation](self_evolution_experiment.py#L123)

---

### Stage 1 Exit Rules
**To advance**: AI must identify ≥3 themes under `Key Themes:`

**Format Examples**:
```markdown
✅ Valid:
Key Themes:
1. AI education
- Beginner onboarding
* Monetization strategies

❌ Invalid:
Key Themes: Various ideas (no list)
```

**Visual Guide**:
```
[▢] 0-2 themes → ❌ Stay in Stage 1
[✓] 3+ themes → ✅ Advance to Stage 2
```

### Stage 2 Exit Rules
**To advance**: AI must document ≥2 patterns with:
1. `Pattern 1: <name>`
2. `Evidence: <examples>`
3. `Confidence: High/Medium/Low`

**Example**:
```markdown
Pattern 1: Fear of technical complexity
Evidence: "I always get stuck on coding parts"
Confidence: High
```

## Example Workflow

```plaintext
1. Select stage (e.g., 3 for Signal Scan)
2. Enter your prompt (end with EOF)
3. Receive AI analysis
4. Automatic self-evaluation
5. Results saved to database
```

## Database Schema

Interactions are stored in `self_evo_logs.duckdb` with:
- Timestamps
- Stage identifiers
- Full prompt/response history
- Evaluation scores
- Improvement notes

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

- [ ] Add web interface
- [ ] Implement team collaboration features
- [ ] Add visualization dashboard

## License

MIT License - Free for personal and commercial use