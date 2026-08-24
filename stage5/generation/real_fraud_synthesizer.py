"""
Conditional Gaussian-copula synthesizer for real fraud data.

Learns from a small set of real, labelled fraud rows and samples new
synthetic fraud rows that preserve:
  - categorical joint frequencies (resampled from observed combinations)
  - each continuous column's marginal distribution (empirical, per stratum)
  - the correlation structure between continuous columns (shared Gaussian
    copula correlation matrix, estimated globally for stability with
    small per-stratum counts)

This does NOT invent new attack telemetry (PIN attempts, screen-share,
auth flow, etc.) that these public datasets never captured -- it only
amplifies the signal that is genuinely present in the source data.
"""

import numpy as np
import pandas as pd
from scipy.stats import rankdata, norm


class ConditionalGaussianCopula:
    """Fit on real rows, sample new synthetic rows with matching structure."""

    def __init__(self, min_marginal_size: int = 10):
        self.min_marginal_size = min_marginal_size
        self.cat_cols = []
        self.cont_cols = []
        self.correlation = None
        self.strata = []  # list of dicts: {values: {cat: val}, weight, marginals: {col: sorted array}}
        self.global_marginals = {}

    def fit(self, df: pd.DataFrame, cat_cols: list, cont_cols: list):
        self.cat_cols = cat_cols
        self.cont_cols = cont_cols
        n = len(df)

        # Global rank-based normal scores -> shared correlation matrix.
        # Shared across strata because per-stratum counts are too small
        # (often <100) to estimate a stable multivariate correlation alone.
        z = np.zeros((n, len(cont_cols)))
        for j, col in enumerate(cont_cols):
            vals = df[col].to_numpy(dtype=float)
            ranks = rankdata(vals, method='average')
            u = np.clip(ranks / (n + 1), 1e-6, 1 - 1e-6)
            z[:, j] = norm.ppf(u)
            self.global_marginals[col] = np.sort(vals)

        if len(cont_cols) >= 2:
            self.correlation = np.corrcoef(z, rowvar=False)
            # guard against numerical non-PD matrices
            self.correlation = _nearest_pd_correlation(self.correlation)
        else:
            self.correlation = np.array([[1.0]])

        # Strata = observed categorical combinations.
        if cat_cols:
            grouped = df.groupby(cat_cols, dropna=False)
        else:
            grouped = [((), df)]

        for key, group in grouped:
            if not isinstance(key, tuple):
                key = (key,)
            values = dict(zip(cat_cols, key))
            weight = len(group) / n
            marginals = {}
            for col in cont_cols:
                vals = group[col].to_numpy(dtype=float)
                if len(vals) >= self.min_marginal_size:
                    marginals[col] = np.sort(vals)
                else:
                    marginals[col] = self.global_marginals[col]
            self.strata.append({'values': values, 'weight': weight, 'marginals': marginals})

        return self

    def sample(self, n: int, random_state: int = 42) -> pd.DataFrame:
        rng = np.random.default_rng(random_state)
        weights = np.array([s['weight'] for s in self.strata])
        weights = weights / weights.sum()
        counts = rng.multinomial(n, weights)

        rows = []
        for stratum, count in zip(self.strata, counts):
            if count == 0:
                continue
            z = rng.multivariate_normal(
                mean=np.zeros(len(self.cont_cols)),
                cov=self.correlation,
                size=count,
            )
            u = norm.cdf(z)
            block = {}
            for j, col in enumerate(self.cont_cols):
                block[col] = _inverse_empirical_cdf(stratum['marginals'][col], u[:, j])
            for col, val in stratum['values'].items():
                block[col] = np.full(count, val)
            rows.append(pd.DataFrame(block))

        out = pd.concat(rows, ignore_index=True)
        out = out.sample(frac=1.0, random_state=random_state).reset_index(drop=True)
        return out[self.cat_cols + self.cont_cols]


def _inverse_empirical_cdf(sorted_vals: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Map uniform(0,1) samples through an empirical quantile function."""
    m = len(sorted_vals)
    idx = u * (m - 1)
    lo = np.floor(idx).astype(int)
    hi = np.ceil(idx).astype(int)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _nearest_pd_correlation(corr: np.ndarray) -> np.ndarray:
    """Clip a near-PD correlation matrix (from small-sample noise) to PD."""
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    eigvals, eigvecs = np.linalg.eigh(corr)
    eigvals = np.clip(eigvals, 1e-6, None)
    fixed = eigvecs @ np.diag(eigvals) @ eigvecs.T
    d = np.sqrt(np.diag(fixed))
    fixed = fixed / np.outer(d, d)
    np.fill_diagonal(fixed, 1.0)
    return fixed


def fidelity_report(real: pd.DataFrame, synth: pd.DataFrame, cont_cols: list, cat_cols: list) -> dict:
    """Compare real vs synthetic distributions -- for the write-up's fidelity evidence."""
    report = {'continuous': {}, 'categorical': {}}
    for col in cont_cols:
        r, s = real[col].to_numpy(dtype=float), synth[col].to_numpy(dtype=float)
        report['continuous'][col] = {
            'real_mean': float(np.mean(r)), 'synth_mean': float(np.mean(s)),
            'real_std': float(np.std(r)), 'synth_std': float(np.std(s)),
            'real_p50': float(np.percentile(r, 50)), 'synth_p50': float(np.percentile(s, 50)),
            'real_p90': float(np.percentile(r, 90)), 'synth_p90': float(np.percentile(s, 90)),
        }
    for col in cat_cols:
        r_freq = real[col].value_counts(normalize=True).to_dict()
        s_freq = synth[col].value_counts(normalize=True).to_dict()
        report['categorical'][col] = {'real': r_freq, 'synth': s_freq}
    return report
