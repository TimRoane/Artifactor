import numpy as np

from artifactor.contracts import OmicsMatrix
from artifactor.diagnostics import bh_adjust, robust_matrix


def matrix(values: np.ndarray) -> OmicsMatrix:
    return OmicsMatrix(
        "x",
        ("a", "b", "c"),
        tuple(f"f{i}" for i in range(values.shape[1])),
        values,
        np.isnan(values),
    )


def test_invariant_features_are_removed_and_missingness_not_mutated() -> None:
    raw = np.array([[1.0, 1.0, np.nan], [1.0, 2.0, 4.0], [1.0, 3.0, 6.0]])
    original = raw.copy()
    scaled, features, _ = robust_matrix(matrix(raw))
    assert features == ("f1", "f2")
    assert np.isfinite(scaled).all()
    np.testing.assert_equal(raw, original)


def test_constant_shift_does_not_change_scaled_values() -> None:
    raw = np.array([[1.0, 3.0], [2.0, 8.0], [4.0, 10.0]])
    left = robust_matrix(matrix(raw))[0]
    right = robust_matrix(matrix(raw + np.array([100.0, -7.0])))[0]
    np.testing.assert_allclose(left, right)


def test_benjamini_hochberg() -> None:
    np.testing.assert_allclose(bh_adjust(np.array([0.01, 0.04, 0.03])), [0.03, 0.04, 0.04])
