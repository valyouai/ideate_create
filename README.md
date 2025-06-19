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

| Stage | Focus Area | Key Activities |
|-------|------------|----------------|
| 0 | Ideation | Raw idea generation |
| 1 | Signal Gathering | Collect external inputs |
| 2 | Pattern Recognition | Identify trends |
| 3 | **Signal Scan** | Deep dive & synthesis |
| 4 | Prototyping | Build quick tests |
| 5 | Implementation | Execute best ideas |

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