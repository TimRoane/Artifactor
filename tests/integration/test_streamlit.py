from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from artifactor.pipeline import analyze
from artifactor.simulation import simulate


def test_home_opens_as_guided_start_screen() -> None:
    application = AppTest.from_file(str(Path("app/Home.py").resolve()))
    application.run(timeout=20)
    assert not application.exception
    assert {"Analyze my data", "Try a demonstration", "Open a completed run"}.issubset(
        {button.label for button in application.button}
    )
    application.button(key="launch-analyze").click().run(timeout=20)
    assert not application.exception
    assert len(application.file_uploader) == 2
    next(
        button for button in application.button if button.label == "← Back to workspace"
    ).click().run(timeout=20)
    application.button(key="launch-demo").click().run(timeout=20)
    assert not application.exception
    assert application.selectbox[0].value == "separable"
    next(
        button for button in application.button if button.label == "← Back to workspace"
    ).click().run(timeout=20)
    application.button(key="launch-open").click().run(timeout=20)
    assert not application.exception
    assert any(button.label == "Open run" for button in application.button)


@pytest.mark.parametrize("scenario", ["separable", "confounded", "ngs_separable"])
def test_all_pages_load_without_recomputation(tmp_path: Path, scenario: str) -> None:
    cohort = tmp_path / "ui"
    simulate(scenario, cohort, seed=11, samples=24, rna_features=40, protein_features=24)
    run = analyze(cohort / "config.yaml")
    app_root = Path("app").resolve()
    pages = [app_root / "Home.py", *sorted((app_root / "pages").glob("*.py"))]
    timestamps = {path: path.stat().st_mtime_ns for path in run.rglob("*") if path.is_file()}
    for page in pages:
        application = AppTest.from_file(str(app_root / "Home.py"))
        application.session_state["run_dir"] = run
        application.run(timeout=20)
        if page.name != "Home.py":
            application.switch_page(str(page.relative_to(app_root))).run(timeout=20)
        assert not application.exception, f"{page} failed: {application.exception}"
        assert any(button.label == "← Choose another run" for button in application.button)
        if page.name == "Home.py":
            next(
                button for button in application.button if button.label == "← Choose another run"
            ).click().run(timeout=20)
            assert not application.exception
            assert any(button.label == "Analyze my data" for button in application.button)
            assert "run_dir" not in application.session_state
    assert timestamps == {
        path: path.stat().st_mtime_ns for path in run.rglob("*") if path.is_file()
    }
