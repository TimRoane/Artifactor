# README visuals

These assets are stored in the repository so the README does not depend on an external image host.

| Asset | Source |
| --- | --- |
| `artifactor-banner.svg` | Editable vector illustration of the project's intent. The matrix is schematic, not experimental data. |
| `../workflow.svg` | Editable vector diagram of the analysis and correction-refusal paths. |
| `correction-report.png` | Browser capture of the actual offline report's correction-comparison section. Only the capture area is selected; the application content and plotted values are unchanged. |

## Screenshot provenance

- Package version: **0.5.0**.
- Scenario: **`separable`**, generated locally from the included simulator.
- Seed: **`20260805`**.
- Dimensions: **240 samples, 2,000 RNA features, 500 protein features**.
- Analysis budget: **`quick`**, with 99 permutations and 20 bootstrap iterations.
- Selected method: **`residualize`**; corrected RNA and protein exports are available.
- Source run fingerprint: **`416ee0cec0e2`**. Local paths participate in configuration normalization, so another checkout can produce a different run fingerprint.
- Capture: headless Chrome, a 1,440-pixel-wide browser viewport, and the first 820 pixels of the report's correction-comparison section.

All samples are synthetic. The screenshot contains no uploaded study data. It demonstrates application behavior, not external or clinical validation.

## Recreate the report

From the repository root after installation:

```bash
uv run artifactor simulate --scenario separable --seed 20260805 --output demo/readme-separable
uv run artifactor analyze --config demo/readme-separable/config.yaml
```

Open `report/artifactor-report.html` in the run directory printed by `analyze`. Navigate to **Correction Comparison**, let the interactive plots finish rendering, and capture the section heading, export decision, and first chart. Keep the screenshot caption and this provenance record aligned if the scenario or software version changes.

The SVGs use explicit backgrounds, system fonts, and accessible titles and descriptions. They can be edited as text and rendered directly by a browser.
