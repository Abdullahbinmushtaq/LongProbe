# LongProbe terminal demonstrations

The recording scripts demonstrate the implemented v0.2.0 Python interface with fixed sample documents and an in-memory retriever. They exercise real selection, scoring, comparison, and policy-gated SQLite promotion. They do not benchmark a vector database or call an embedding model.

## Run the scenarios

From the repository root, with Python 3.11 or newer:

```bash
make setup-demos
make check-demos
```

The dedicated `demos/.recording_venv` directory is generated and rebuilt by setup. The legacy `demos/.demo_venv` directory is not used: it contains machine-specific files and may have broken Python links.

Setup installs this checkout into `demos/.recording_venv`; it does not install an older published package or download embedding models. Package installation may need network access. Once installed, these scenarios run without external services. Each run uses temporary golden/configuration/baseline files and cleans them up afterward.

Run an individual scenario with recording pauses:

```bash
demos/.recording_venv/bin/python demo_run/complete_workflow.py
demos/.recording_venv/bin/python demo_run/monitor_rag_quality.py
demos/.recording_venv/bin/python demo_run/detect_regressions.py
```

Add `--no-delay` for immediate output.

## What the recordings show

| Recording source | Scenario |
|---|---|
| `01-complete-workflow.tape` | Draft candidates, source-review explanation, approved cases, eligible promotion, and missing-evidence regression |
| `01-quick-check.tape` | One evaluation with per-question results and shared quality verdict |
| `02-python-api.tape` | The Python report, 85% threshold, and visible absence of a historical reference |
| `03-baseline-tracking.tape` | Explicit `production-v1` selection, compatibility, regression/improvement counts, and quality failure |

The workflow uses fixed sample evidence supplied with the script. Its scripted status transition illustrates a review decision; it does not perform human approval. Real generated or captured evidence must be checked against source documents before approval.

The regression scenarios deliberately remove refund evidence after promotion. The second evaluation reports one regression and failed quality. The script checks this expected result and exits successfully; the illustrated passing-quality assertion would fail in an application test. The saved reference is preserved.

## Regenerate README and documentation GIFs

Install [VHS and its recording prerequisites](https://github.com/charmbracelet/vhs#installation), including ttyd, Chromium, and ffmpeg. Then run from the repository root:

```bash
make demos
```

This records the four existing tapes into `demos/` and copies the resulting GIFs into both `assets/` and `docs/assets/`. Commit the tapes, scripts, and regenerated assets together when recording tools are available. Changing a script alone does not update an existing GIF.

The v0.2.0 source update was executed and verified locally, but the existing GIFs have not yet been regenerated because VHS is absent in the implementation environment. They remain historical illustrations until that recording step is completed.

To record individually:

```bash
vhs demos/01-complete-workflow.tape
vhs demos/01-quick-check.tape
vhs demos/02-python-api.tape
vhs demos/03-baseline-tracking.tape
```

Individual recording does not perform the asset-copy steps. Use `make demos` to synchronize the files displayed in the README and documentation.

## Editing presentation

Keep the existing theme, font, dimensions, and README layout. Adjust tape pauses if a scenario needs more reading time. Display the quality verdict and comparison compatibility alongside recall; a good average or zero regression count alone does not establish deployment readiness.
