# Complete workflow

![Complete Workflow](../assets/01-complete-workflow.gif)

The v0.2.0 recording uses the original terminal dashboard style: progress panels, result tables, and a quality verdict. No Python source code is displayed. Recording instructions are in `demos/README.md`.

## Current recording scenario

The self-contained demonstration uses three sample questions and fixed source evidence. It runs real LongProbe evaluation and baseline promotion through a deterministic in-memory adapter, without a vector database, embedding model, or external API.

1. Prepare candidate questions with `draft` status.
2. Show the source evidence and explain the review required before approval. The scripted fixture uses pre-reviewed sample evidence; it does not perform a human review.
3. Evaluate approved questions with an 85% threshold and show each question's result.
4. Explicitly promote the eligible report under `production-v1` using the default `all_questions` policy.
5. Remove refund evidence from the sample retriever without changing the golden requirements.
6. Evaluate against the explicitly selected reference, showing compatibility, regression/improvement counts, lost evidence, and failed quality.

The first evaluation passes at 100%. The second reports 66.7% recall, one regression, and failed quality. The original baseline remains intact. The recording uses fixed sample evidence so these results are reproducible.

## Run locally

From the repository root:

```bash
make setup-demos
demos/.recording_venv/bin/python demo_run/complete_workflow.py
```

Add `--no-delay` to skip presentation pauses. Each run uses temporary project files and removes them afterward.

## Main API calls

After reviewing evidence and configuring the probe:

```python
report = probe.run()
assert report.quality["passed"], report.quality["reasons"]
probe.save_baseline(label="production-v1")

# After the application's retrieval behavior changes:
report2 = probe.run(baseline_label="production-v1")
diff = report2.comparison
print(f"Compatible: {diff['compatible']}")
print(f"Regressions: {len(diff['regressions'])}")
print(f"Improvements: {len(diff['improvements'])}")
assert report2.quality["passed"], report2.quality["reasons"]
```

The final assertion fails for the deliberate regression. The demonstration verifies that expected failure and shows a quality verdict in the dashboard, without displaying code or a traceback.

See [golden review](../guide/golden-questions.md), [baseline management](../guide/baseline-management.md), and [release behavior](../releases/v0.2.0.md).
