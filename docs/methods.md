# Methods

Confounding is checked before correction because downstream performance cannot recover information absent from the design. Artifactor encodes declared biological, protected, and technical variables, reports rank and condition number, and evaluates categorical overlap plus corrected Cramér's V, eta-squared, or absolute Spearman association. A protected variable aligned perfectly with a technical variable blocks correction.

Within each modality, features are median-centered and MAD-scaled, falling back to standard deviation. Missing values are median-filled only for decomposition; correction outputs restore the original missingness mask. Randomized PCA has a recorded seed and deterministic component orientation. Joint `block_pca` scales each modality block to unit Frobenius norm before concatenation.

Categorical metadata uses eta-squared and continuous metadata uses absolute Spearman correlation. Permutation p-values are FDR-adjusted within modality-variable families. Feature-wise partial technical variance compares nested biological/protected and full models, with negative presentation values clamped while raw values remain available.

Residualization estimates a joint design and removes only fitted technical columns. The Python-native batch harmonizer removes protected-covariate fit, aligns categorical batch residual location and scale, then restores protected fit. Evaluation fits prediction models inside cross-validation folds and compares technical predictability with biological retention; mapped features provide a cross-modal concordance check. The recommendation requires material technical removal with no more than five percent declared biological loss.

The system detects statistical consistency, not root cause. Findings therefore include their evidence, an explicit limitation, and a proposed replicated or bridged wet-lab experiment.
