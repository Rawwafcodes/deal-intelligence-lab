from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIRED = {
    "00-README.md",
    "AGENTS.md",
    "01-current-state.md",
    "02-product-integration.md",
    "03-architecture.md",
    "04-revised-roadmap.md",
    "05-task-14.2-integrity-review.md",
    "06-m15-change-awareness.md",
    "07-m16-continuous-integrity.md",
    "08-acceptance-and-evaluation.md",
    "09-decisions-and-non-goals.md",
    "10-adoption-prompt.md",
    "CHANGELOG.md",
}


def main() -> None:
    actual = {path.name for path in ROOT.iterdir() if path.is_file()}
    missing = sorted(REQUIRED - actual)
    if missing:
        raise SystemExit(f"Missing required files: {', '.join(missing)}")

    roadmap = (ROOT / "04-revised-roadmap.md").read_text(encoding="utf-8")
    prompt = (ROOT / "10-adoption-prompt.md").read_text(encoding="utf-8")
    task = (ROOT / "05-task-14.2-integrity-review.md").read_text(encoding="utf-8")

    assertions = {
        "roadmap preserves M13.2": "13.2 Version-specific review lifecycle" in roadmap,
        "roadmap places integration at M14.2": "14.2 Work-product Integrity Review" in roadmap,
        "roadmap adds M16": "M16 — Continuous workspace integrity" in roadmap,
        "adoption forbids immediate M14 implementation": "Do not implement M14–M16" in prompt,
        "task requires shared findings": "existing shared findings register" in task,
        "task requires human checkpoint": "Human checkpoint" in task,
    }
    failed = [name for name, passed in assertions.items() if not passed]
    if failed:
        raise SystemExit(f"Package assertions failed: {', '.join(failed)}")

    print(f"PASS: {len(REQUIRED)} required files and {len(assertions)} integration assertions")


if __name__ == "__main__":
    main()
