from pathlib import Path

from streamlit.testing.v1 import AppTest

from artifactor.pipeline import analyze
from artifactor.simulation import simulate


def test_all_pages_load_without_recomputation(tmp_path: Path) -> None:
    cohort = tmp_path / "ui"
    simulate("separable", cohort, seed=11, samples=24, rna_features=40, protein_features=24)
    run = analyze(cohort / "config.yaml")
    app_root = Path("app").resolve()
    pages = [app_root / "Home.py", *sorted((app_root / "pages").glob("*.py"))]
    timestamps = {path: path.stat().st_mtime_ns for path in run.rglob("*") if path.is_file()}
    for page in pages:
        application = AppTest.from_file(str(page))
        application.session_state["run_dir"] = run
        application.run(timeout=20)
        assert not application.exception, f"{page} failed: {application.exception}"
    assert timestamps == {
        path: path.stat().st_mtime_ns for path in run.rglob("*") if path.is_file()
    }
