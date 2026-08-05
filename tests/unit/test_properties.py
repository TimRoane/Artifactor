import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from artifactor.contracts import OmicsMatrix
from artifactor.diagnostics import robust_matrix


def as_matrix(values: np.ndarray) -> OmicsMatrix:
    return OmicsMatrix(
        "x",
        tuple(f"s{i}" for i in range(values.shape[0])),
        tuple(f"f{i}" for i in range(values.shape[1])),
        values,
        np.isnan(values),
    )


@given(st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False))
def test_adding_constant_preserves_robust_latent_input(offset: float) -> None:
    values = np.arange(30, dtype=float).reshape(10, 3) + np.array([0.0, 2.0, -3.0])
    np.testing.assert_allclose(
        robust_matrix(as_matrix(values))[0],
        robust_matrix(as_matrix(values + offset))[0],
        atol=1e-10,
    )


def test_feature_reordering_preserves_scalar_variance() -> None:
    values = np.random.default_rng(4).normal(size=(20, 5))
    left = robust_matrix(as_matrix(values))[0]
    right = robust_matrix(as_matrix(values[:, ::-1]))[0]
    np.testing.assert_allclose(np.sort(np.var(left, axis=0)), np.sort(np.var(right, axis=0)))
