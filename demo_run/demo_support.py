"""Self-contained v0.2.0 recording scenarios using the real evaluation API."""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from longprobe import LongProbe
from longprobe.adapters import AbstractRetrieverAdapter
from longprobe.core.golden import GoldenQuestion, GoldenSet

# Fixed source evidence keeps recordings reproducible without SDKs or model downloads.
CASES = [
    ("refund", "What is the refund policy?", "Refunds are available within 30 days."),
    ("payment", "What are the payment terms?", "Enterprise payment terms are net 60 days."),
    ("security", "How is data encrypted?", "Data is encrypted at rest using AES-256."),
]


class SampleRetriever(AbstractRetrieverAdapter):
    """Deterministic sample retriever; this is not a vector database benchmark."""

    def __init__(self):
        self.missing = set()
        self.calls = 0

    def retrieve(self, query, top_k=5):
        self.calls += 1
        return [
            {"id": key, "text": evidence, "score": 1.0, "metadata": {"source": "sample"}}
            for key, question, evidence in CASES
            if query == question and key not in self.missing
        ][:top_k]


def show_report(console, report):
    table = Table(title="Retrieval results")
    for heading in ("Question", "Recall", "Required evidence", "Result"):
        table.add_column(heading)
    for result in report.results:
        table.add_row(
            result.question_id,
            f"{result.recall_score:.0%}",
            f"{len(result.found_chunks)}/{len(result.required_chunks)}",
            "PASS" if result.passed else "FAIL",
        )
    console.print(table)
    passed = report.quality["passed"]
    console.print(
        Panel(
            f"Overall recall: {report.overall_recall:.1%}\n"
            f"Pass rate: {report.pass_rate:.1%}\n"
            f"Quality: {'PASS' if passed else 'FAIL'}\n"
            f"Reference status: {report.baseline_identity['status']}",
            title="Shared quality verdict",
            border_style="green" if passed else "red",
        )
    )
    for reason in report.quality["reasons"]:
        console.print(reason, style="red")


def run_demo(mode):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-delay", action="store_true", help="Run without recording pauses")
    args = parser.parse_args()
    console = Console()

    def command(code):
        console.print(Syntax(code, "python", theme="monokai", word_wrap=True))
        if not args.no_delay:
            time.sleep(1.5)

    title = {
        "workflow": "Complete retrieval regression workflow",
        "quality": "Monitor retrieval quality",
        "regression": "Compare against a selected baseline",
    }[mode]
    console.print(Panel(f"LongProbe v0.2.0 | {title}", border_style="cyan"))
    console.print("Synthetic sample data | temporary files | no external services", style="dim")

    with tempfile.TemporaryDirectory(prefix="longprobe-demo-") as directory:
        root = Path(directory)
        goldens_path = root / "goldens.yaml"
        config_path = root / "longprobe.yaml"
        suite = GoldenSet(
            name="reviewed-sample-documents",
            version="1.0",
            questions=[
                GoldenQuestion(
                    id=key,
                    question=question,
                    required_chunks=[evidence],
                    match_mode="text",
                    status="draft" if mode == "workflow" else "approved",
                    top_k=3,
                )
                for key, question, evidence in CASES
            ],
        )
        suite.to_yaml(str(goldens_path))
        config_path.write_text(
            yaml.safe_dump(
                {
                    "scoring": {"recall_threshold": 0.85},
                    "baseline": {
                        "db_path": str(root / "baselines.db"),
                        "quality_gate": "all_questions",
                        "auto_compare": True,
                    },
                }
            )
        )
        adapter = SampleRetriever()
        if mode == "workflow":
            console.print("1. Prepare draft candidates from sample evidence", style="bold cyan")
            console.print("Automatic retrieval alone does not establish correct evidence.")
            command('question.status = "draft"')
            console.print("2. Review source evidence before approval", style="bold cyan")
            console.print(
                "This scripted example uses fixed, pre-reviewed sample evidence. "
                "In your project, a person must verify each requirement before approval."
            )
            table = Table("Question", "Reviewed source evidence")
            for _, question, evidence in CASES:
                table.add_row(question, evidence)
            console.print(table)
            for question in suite.questions:
                question.status = "approved"
            suite.to_yaml(str(goldens_path))
            command(
                'question.status = "approved"  # Only after source review\nsuite.to_yaml(goldens_path)'
            )

        console.print("Evaluate approved questions at an 85% threshold", style="bold cyan")
        command(
            "probe = LongProbe(adapter=adapter, goldens_path=goldens_path, config_path=config_path)\n"
            "report = probe.run()\n"
            'assert report.quality["passed"], report.quality["reasons"]'
        )
        probe = LongProbe(
            adapter=adapter, goldens_path=str(goldens_path), config_path=str(config_path)
        )
        report = probe.run()
        show_report(console, report)
        assert report.quality["passed"], report.quality["reasons"]
        assert adapter.calls == len(CASES)
        if mode == "quality":
            console.print(
                "Retrieval quality checks passed for these three reviewed cases.", style="green"
            )
            console.print("One evaluation; no baseline was promoted automatically.")
            return

        console.print("Explicitly promote the eligible report", style="bold cyan")
        command('probe.save_baseline(label="production-v1")')
        probe.save_baseline(label="production-v1")
        console.print("Baseline saved: production-v1 | policy: all_questions", style="green")
        assert adapter.calls == len(CASES), "Promotion must reuse the retained evaluation"

        console.print("Simulate a retrieval change: refund evidence is now missing", style="yellow")
        adapter.missing.add("refund")
        command(
            'report2 = probe.run(baseline_label="production-v1")\n'
            "diff = report2.comparison\n"
            "print(f\"Regressions: {len(diff['regressions'])}\")\n"
            "print(f\"Improvements: {len(diff['improvements'])}\")"
        )
        report2 = probe.run(baseline_label="production-v1")
        diff = report2.comparison
        show_report(console, report2)
        console.print(f"Reference: {report2.baseline_identity['resolved_label']}")
        console.print(f"Compatible: {diff['compatible']}")
        console.print(f"Regressions: {len(diff['regressions'])}")
        console.print(f"Improvements: {len(diff['improvements'])}")
        for regression in diff["regressions"]:
            console.print(
                f"{regression['question_id']}: lost required evidence: "
                f"{regression['newly_lost_chunks']}",
                style="red",
            )
        command('assert report2.quality["passed"], report2.quality["reasons"]')
        console.print(
            "The quality assertion would fail: review the missing refund evidence.", style="red"
        )
        console.print("Expected demonstration failure; the trusted baseline remains unchanged.")
        assert not report2.quality["passed"]
        assert diff["compatible"] and len(diff["regressions"]) == 1
        assert adapter.calls == 2 * len(CASES)
        assert probe.baseline_store.load("production-v1").overall_recall == 1.0
