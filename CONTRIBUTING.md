# Contributing

Artifactor is proprietary and available for source inspection under [LICENSE](LICENSE). Public access does not authorize running, testing, or modifying the software.

You may discuss the published design and report observations from reading the source. Before preparing a code contribution, obtain separate written permission covering development and testing, and agree with the maintainer on the terms for incorporating your contribution. Opening an issue or submitting a request does not itself grant that permission.

The following conventions apply to maintainers and contributors with the necessary authorization.

Use Python 3.12 and `uv sync --all-extras`. Keep scientific algorithms independent of I/O, seed every stochastic operation, add focused tests, and run Ruff, mypy, and pytest before submitting changes. Report associations with calibrated language; never convert them into causal or clinical claims.
