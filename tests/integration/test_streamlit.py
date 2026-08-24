from pathlib import Path

from streamlit.testing.v1 import AppTest

from artifactor.pipeline import analyze
from artifactor.simulation import simulate


def test_home_opens_as_guided_start_screen() -> None:
    application = AppTest.from_file(str(Path("app/Home.py").resolve()))
    application.run(timeout=20)
    assert not application.exception
    assert application.title[0].value == "Start an Artifactor analysis"
    assert len(application.file_uploader) == 2


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
        assert any(button.label == "← Choose another run" for button in application.button)
        if page.name == "Home.py":
            next(
                button
                for button in application.button
                if button.label == "← Choose another run"
            ).click().run(timeout=20)
            assert not application.exception
            assert application.title[0].value == "Start an Artifactor analysis"
            assert "run_dir" not in application.session_state
    assert timestamps == {
        path: path.stat().st_mtime_ns for path in run.rglob("*") if path.is_file()
    }
