# Local model integration

AgentForge can generate file-edit proposals using a locally running [Ollama](https://ollama.com) model.

Install Ollama separately and download a coding model appropriate for your machine. Verify it is available:

```bash
ollama list
```

Then run the sample task from the repository root. Replace `YOUR_MODEL` with a model listed by Ollama.

```bash
agentforge task solve benchmarks/sample_cases/syntax_fix.json   --model YOUR_MODEL   --file src/example.py   --output runs/model_evaluations.jsonl
```

For each run, AgentForge sends the selected source files and task title to the local Ollama server, validates the returned edits, and evaluates the proposed changes in a temporary repository copy. The original files are preserved.

The local endpoint is `127.0.0.1:11434`. Only explicitly selected source files are included in the model request. Run coding checks only against repositories you trust.
