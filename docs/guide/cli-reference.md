# CLI Reference

Use `longprobe COMMAND --help` for all implemented options. Unless overridden, golden/config paths are `goldens.yaml` and `longprobe.yaml`.

| Command | Purpose |
|---|---|
| `init` | Create example files; preserve existing files unless `--force` |
| `check` | Evaluate selected approved questions against the configured retriever |
| `capture` | Query supplied questions and select evidence; `--auto` creates drafts |
| `generate PATH` | Generate questions from document text |
| `edit` | Review statuses, edit question text/mode, approve drafts, and save |
| `baseline save` | Evaluate approved questions and save a labeled snapshot subject to the existing overall-recall gate |
| `baseline list` | List snapshots at `--db-path` |
| `baseline delete --label LABEL` | Delete a snapshot at `--db-path` |
| `diff --baseline LABEL` | Compare a live run with a stored snapshot |
| `diff LABEL_A LABEL_B` | Compare two stored snapshots |
| `explain QUESTION_ID` | Rerun evaluation and show a question's requirements and missing evidence |
| `watch` | Poll the golden file and rerun after changes |

## Common evaluation options

```bash
longprobe check --goldens tests/goldens.yaml --config longprobe.yaml
longprobe check --threshold 0.9 --top-k 10
longprobe check --tag critical --tag billing
longprobe check --include-drafts
longprobe check --output json
longprobe check --output github
```

Multiple tags require all specified tags. Empty input, no matching tags, and no approved selected questions fail rather than pass. `--include-drafts` does not allow a genuinely empty evaluation. Configuration/input errors fail even when `fail_on_regression` is false.

JSON output can still contain notices or command-specific trailing status text; a general machine-output cleanup is deferred. The default pytest adapter fixture also remains limited; supply your own adapter fixture. Explanations do not implement rank deltas or distance-drop analysis.

## Generation and capture

```bash
longprobe capture --question "What is the refund policy?" --auto
longprobe capture --questions-file questions.txt --match-mode id
longprobe generate ./documents --num-questions 20 --auto-capture
longprobe edit
```

Generate requires the optional generation dependencies and a configured provider/model. Auto-capture requires a retriever and saves drafts. Existing invalid/unreadable goldens fail preflight before LLM/retrieval calls and are never reset automatically.

Question-list export is a separate mode:

```bash
longprobe generate ./documents --output questions.yaml
longprobe generate ./documents --output questions.yaml --overwrite
```

The second command explicitly replaces an existing question-list output. `--overwrite` requires `--output` and cannot be combined with `--auto-capture`. `--output` and `--auto-capture` cannot be combined. Exported question lists need verified expected evidence before evaluation; they are not editable golden sets.

## Baselines and watch

```bash
longprobe baseline save --label latest
longprobe baseline list --db-path .longprobe/baselines.db
longprobe diff --baseline latest
longprobe watch --interval 2
```

Saving another label does not update `latest`. Baseline-save policy and historical comparison behavior are unchanged by this reliability patch. Watch runs only after a golden-file change, not immediately or on configuration/index changes. A failed watch iteration is reported and the watcher keeps waiting.

See [configuration and recovery](../getting-started/configuration.md) and the [quick start](../getting-started/quick-start.md).
