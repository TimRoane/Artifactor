# README visuals

The README uses actual captures of the redesigned Streamlit application. Images are stored in this repository so they do not depend on an external image host.

## Current workspace screenshots

Captured on **2026-09-13**, from frontend revision **`4f1583b`**. The package identifies itself as **0.5.0**; the frontend redesign is recorded under **Unreleased** in the [changelog](../../CHANGELOG.md).

| Asset | Screen | Data shown |
| --- | --- | --- |
| [workspace.png](workspace.png) | Workspace landing page | No active study. The matrix illustration is conceptual. |
| [study-setup.png](study-setup.png) | New-study upload screen | Empty inputs; no uploaded files or study data. |
| [results-overview.png](results-overview.png) | Decision and downloads | Saved `separable` synthetic run. |
| [factor-explorer.png](factor-explorer.png) | Factor–metadata associations | Saved `separable` run, `block_pca` modality. |
| [correction-comparison.png](correction-comparison.png) | Preservation/removal comparison | Saved `separable` run. |
| [evidence-follow-up.png](evidence-follow-up.png) | Evidence and proposed experiments | Saved `separable` run. |
| [correction-refused.png](correction-refused.png) | Refused correction and export decision | Saved `confounded` synthetic run. |

Captures use headless Chrome at **1600 × 1060 pixels**, device scale 1, and the application's light theme. These are browser viewport captures: visible application content, labels, and plotted values have not been replaced or retouched. Screens were captured after rendering, with no application exceptions or horizontal page overflow.

### Synthetic run provenance

| Setting | Separable example | Confounded example |
| --- | --- | --- |
| Source | Included simulator, guided-demo dimensions | Included simulator, CLI-default dimensions |
| Seed | `20260805` | `20260805` |
| Samples | 80 | 240 |
| RNA features | 500 | 2,000 |
| Protein features | 150 | 500 |
| Budget | `quick` | `quick` |
| Permutations / bootstrap iterations | 99 / 20 | 99 / 20 |
| Run fingerprint | `44735b4f887a` | `b255a9fcf9a9` |
| Recommendation | `residualize` | `none` |
| Corrected-data export | Available | Not generated |

The two runs illustrate different decision outcomes; their different cohort sizes mean the screenshots are **not** a controlled performance comparison. Local paths participate in normalized configuration, so another checkout can produce different run fingerprints.

All result data are synthetic. No private or uploaded research datasets are shown. Screenshots demonstrate application behavior, not external or clinical validation.

## Recreate the displayed workflows

These instructions are for maintainers and users with separate written permission to run Artifactor under [LICENSE](../../LICENSE).

For the separable example:

1. Run `uv run artifactor start`.
2. Select **Try a demonstration**.
3. Choose **Correction is safe: biology and batch overlap** and select **Run demo**.
4. Open **Factor explorer**, **Correction comparison**, and **Evidence & follow-up** from the sidebar. Select `block_pca` for the displayed factor view.
5. Capture each screen after the plots finish rendering.

The guided demonstration generates 80 samples with 500 RNA and 150 protein features. For the 240-sample refusal example:

```bash
uv run artifactor simulate --scenario confounded --seed 20260805 --output demo/readme-confounded
uv run artifactor analyze --config demo/readme-confounded/config.yaml
```

Use **Open a completed run** to open the directory printed by `analyze`. The overview displays the non-identifiable design and the explained refusal.

The landing and empty setup screens do not need a completed run. Capture them before selecting or uploading any study. Keep captions and this record aligned when updating screenshots.

## Supporting and earlier assets

- [workflow.svg](../workflow.svg) is an editable vector diagram of the analysis and correction-refusal paths, still used in the README.
- [artifactor-banner.svg](artifactor-banner.svg) is the earlier conceptual banner. The current README leads with the real workspace instead.
- [correction-report.png](correction-report.png) is the earlier offline HTML report capture, retained as a reference. It uses the 240-sample `separable` simulation, 2,000 RNA features, 500 protein features, seed `20260805`, quick budget, and run fingerprint `416ee0cec0e2`. It was captured from a 1,440-pixel-wide viewport, selecting the first 820 pixels of the correction-comparison section.

The vector assets have explicit backgrounds, system fonts, and accessible titles and descriptions. They are diagrams, not measured results.
