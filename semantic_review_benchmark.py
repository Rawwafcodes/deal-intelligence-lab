#!/usr/bin/env python3
"""M16.4 semantic review benchmark - "current strong-model review" leg
only, on explicit, scope-bounded founder authorization.

The M16.4 spec asks for three benchmarked legs: current strong-model
review, retrieval-gated strong-model review, and an NLI-plus-model
pipeline. This script builds and runs ONLY the first leg. The other two
are deliberately not attempted here: building either for real means
building exactly the infrastructure the roadmap explicitly defers
pending measured evidence (embeddings/vector retrieval for
retrieval-gating; a dedicated NLI model for the third leg) - a circular
dependency this task does not try to resolve by building throwaway
infrastructure just to have something to benchmark. See this task's own
completion file (docs/workspace-shift/tasks/16.4-semantic-review-
benchmark.md) for the full disclosure.

Calls `integrity_review.run_integrity_review` directly - the pure
analytical capability - bypassing the mandate/plan/run orchestration
layer, which Tasks 12.1-12.4 and 14.2 already proved separately and which
this benchmark has nothing new to say about. Against three real,
synthetic-but-realistic PDF submission/source pairs, each hand-authored
to mirror one of Task 16.1's own seeded golden cases (numerical_conflict,
logical_contradiction, modality_escalation) as closely as a generic
taxonomy example allows.

Usage:
    ./venv/bin/python semantic_review_benchmark.py              # dry run, zero cost
    ./venv/bin/python semantic_review_benchmark.py --confirm    # real, paid Anthropic calls

Dry run (the default) creates every real project/task/work-product/
document record and every real PDF file, and prints exactly what would be
sent - this is how the harness itself was built and tested, at zero cost.
Only --confirm makes real network calls, and does so only against the
project this script itself just created (never Universal Logic or any
other pre-existing project).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import documents
import golden_set
import integrity_review
import store
import tasks
import work_products


@dataclass(frozen=True)
class BenchmarkCase:
    defect_type: golden_set.DefectType
    title: str
    submission_title: str
    submission_text: str
    source_title: str
    source_text: str
    pre_registered_expectation: str


CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        defect_type=golden_set.DefectType.NUMERICAL_CONFLICT,
        title="Purchase price conflict",
        submission_title="Acquisition Summary Memo",
        submission_text=(
            "[SYNTHETIC TEST MATERIAL - Task 16.4 benchmark, not a real transaction]\n\n"
            "Acquisition Summary Memo\n\n"
            "Purchase Price: the parties have agreed a Purchase Price of USD 50,000,000, payable "
            "in cash at closing, per the executed Term Sheet for this engagement.\n"
        ),
        source_title="Sources and Uses Workbook Summary",
        source_text=(
            "[SYNTHETIC TEST MATERIAL - Task 16.4 benchmark, not a real transaction]\n\n"
            "Sources and Uses Workbook Summary\n\n"
            "Total Purchase Consideration: USD 52,000,000.\n"
        ),
        pre_registered_expectation=(
            "A candidate classified 'numerical conflict' (severity high or critical) stating that "
            "the submission's USD 50,000,000 purchase price disagrees with the source's "
            "USD 52,000,000 total purchase consideration for what both present as the same figure."
        ),
    ),
    BenchmarkCase(
        defect_type=golden_set.DefectType.LOGICAL_CONTRADICTION,
        title="Exclusivity compliance contradiction",
        submission_title="Exclusivity Compliance Summary",
        submission_text=(
            "[SYNTHETIC TEST MATERIAL - Task 16.4 benchmark, not a real transaction]\n\n"
            "Exclusivity Compliance Summary\n\n"
            "During the Exclusivity Period, Seller has not solicited, negotiated, or entered into "
            "any agreement with any third party regarding a sale of the Company, in full "
            "compliance with Purchase Agreement Section 5.3.\n"
        ),
        source_title="Disclosure Schedule 5.3(a)",
        source_text=(
            "[SYNTHETIC TEST MATERIAL - Task 16.4 benchmark, not a real transaction]\n\n"
            "Disclosure Schedule 5.3(a)\n\n"
            "During the Exclusivity Period, Seller entered into a non-binding term sheet with "
            "Third Party X regarding a potential sale of the Company.\n"
        ),
        pre_registered_expectation=(
            "A candidate flagging that the submission's compliance claim directly contradicts the "
            "disclosure schedule's own disclosed side term sheet with a third party during the "
            "same exclusivity period - a genuine logical contradiction, not merely a numeric or "
            "timing discrepancy."
        ),
    ),
    BenchmarkCase(
        defect_type=golden_set.DefectType.MODALITY_ESCALATION,
        title="Conditional LOI restated as a firm commitment",
        submission_title="Deal Status Summary",
        submission_text=(
            "[SYNTHETIC TEST MATERIAL - Task 16.4 benchmark, not a real transaction]\n\n"
            "Deal Status Summary\n\n"
            "Buyer has committed to acquire the Company on these terms.\n"
        ),
        source_title="Draft Letter of Intent",
        source_text=(
            "[SYNTHETIC TEST MATERIAL - Task 16.4 benchmark, not a real transaction]\n\n"
            "Draft Letter of Intent\n\n"
            "Buyer may, subject to further diligence and financing, elect to proceed with the "
            "acquisition on substantially these terms.\n"
        ),
        pre_registered_expectation=(
            "A candidate flagging that the submission describes the buyer as having 'committed' "
            "when the underlying letter of intent is explicitly conditional and non-binding - a "
            "modality escalation, not a genuine firm commitment."
        ),
    ),
]


def _text_to_pdf_bytes(text: str) -> bytes:
    """Real PDF bytes via the system's own `cupsfilter` (text/plain ->
    application/pdf) - the same tool Tasks 14.2/14.3 used for their own
    live-proof synthetic material, not placeholder bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        txt_path = Path(tmp) / "input.txt"
        txt_path.write_text(text, encoding="utf-8")
        result = subprocess.run(["cupsfilter", str(txt_path)], capture_output=True)
        if result.returncode != 0 or not result.stdout.startswith(b"%PDF"):
            raise RuntimeError(
                f"cupsfilter failed (exit {result.returncode}): "
                f"{result.stderr.decode('utf-8', 'replace')[:2000]}"
            )
        return result.stdout


def build_case_records(
    project_id: str, created_by: str, case: BenchmarkCase
) -> tuple[integrity_review.TargetSelection, integrity_review.SourceSelection]:
    """Creates one real Task, one real PDF work-product submission
    (the target under review), and one real PDF source document - all on
    the caller-supplied scratch project - and returns them wrapped as
    `integrity_review.py`'s own selection dataclasses, ready to pass
    straight into `run_integrity_review`."""
    task = tasks.create_task(
        project_id, title=f"[16.4 benchmark] {case.title}",
        description="Synthetic benchmark case for Task 16.4 (M16 semantic review benchmark).",
        created_by=created_by,
    )

    submission_pdf = _text_to_pdf_bytes(case.submission_text)
    submission_result = work_products.create_work_product(
        project_id, task.id, case.submission_title, f"{case.submission_title}.pdf", submission_pdf, created_by,
    )
    if submission_result.status != "success" or submission_result.work_product is None:
        raise RuntimeError(f"failed to create submission work product: {submission_result.error}")
    work_product = submission_result.work_product
    assert work_product.current_version_id is not None
    work_product_version = work_products.get_version(work_product.id, work_product.current_version_id)
    assert work_product_version is not None

    source_pdf = _text_to_pdf_bytes(case.source_text)
    upload_result = documents.save_uploaded_file(project_id, f"{case.source_title}.pdf", "", source_pdf)
    if upload_result.status != "success" or upload_result.document is None:
        raise RuntimeError(f"failed to upload source document: {upload_result.error}")
    document = upload_result.document
    assert document.current_version_id is not None
    document_version = documents.get_version(document.id, document.current_version_id)
    assert document_version is not None

    target = integrity_review.TargetSelection(work_product=work_product, version=work_product_version)
    source = integrity_review.SourceSelection(document=document, version=document_version)
    return target, source


REVIEW_CONTEXT = (
    "This is Task 16.4's own real, founder-authorized benchmark of the current strong-model "
    "review approach against a small, pre-registered subset of the M16.1 golden set. All content "
    "is synthetic test material, explicitly labeled as such inside the documents themselves."
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--confirm", action="store_true",
        help="Make real, paid Anthropic calls. Without this flag, builds every real record/PDF "
             "and prints what would be sent, at zero cost.",
    )
    parser.add_argument(
        "--case", choices=[c.defect_type.value for c in CASES], default=None,
        help="Run only this one case (by defect type value). Default: all three.",
    )
    args = parser.parse_args()

    store.init_db()
    documents.init_documents_db()
    work_products.init_work_products_db()
    tasks.init_tasks_db()
    golden_set.init_golden_set_db()

    project = store.create_project(
        "Task 16.4 Semantic Review Benchmark (SYNTHETIC)",
        "Disposable scratch project for the M16.4 current-strong-model-review benchmark. "
        "Synthetic content only - never Universal Logic or any other pre-existing project.",
    )
    print(f"Created scratch project {project.id} ({project.name})")

    selected_cases = [c for c in CASES if args.case is None or c.defect_type.value == args.case]
    results: list[dict] = []

    for case in selected_cases:
        print(f"\n=== Case: {case.title} ({case.defect_type.value}) ===")
        target, source = build_case_records(project.id, "benchmark@local.dev", case)
        print(f"  Submission work product: {target.work_product.id} ({target.work_product.original_filename})")
        print(f"  Source document: {source.document.id} ({source.document.original_filename})")
        print(f"  Pre-registered expectation: {case.pre_registered_expectation}")

        if not args.confirm:
            print("  [dry run] not calling the model. Pass --confirm to make a real, paid Anthropic call.")
            results.append({"case": case.defect_type.value, "dry_run": True})
            continue

        outcome = integrity_review.run_integrity_review(target, [source], [], REVIEW_CONTEXT)
        print(f"  success={outcome.success} model={outcome.model} seconds={outcome.analysis_seconds:.1f}")
        if outcome.error_type:
            print(f"  ERROR: {outcome.error_type}: {outcome.error_message}")
        for candidate in outcome.candidates or []:
            print(f"  - [{candidate.classification}] {candidate.title}")
            print(f"      assertion: {candidate.assertion}")
        results.append(
            {
                "case": case.defect_type.value,
                "pre_registered_expectation": case.pre_registered_expectation,
                "outcome": {
                    "success": outcome.success,
                    "model": outcome.model,
                    "analysis_seconds": outcome.analysis_seconds,
                    "usage": outcome.usage,
                    "candidates": [c.to_dict() for c in (outcome.candidates or [])],
                    "error_type": outcome.error_type,
                    "error_message": outcome.error_message,
                },
            }
        )

    out_path = Path(f"benchmark_16_4_results_{uuid.uuid4().hex[:8]}.json")
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote results to {out_path}")


if __name__ == "__main__":
    main()
