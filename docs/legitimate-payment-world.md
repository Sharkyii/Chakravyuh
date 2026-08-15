# Legitimate payment world

Stage 1 generates a deterministic, non-fraud payment baseline from the existing
population generator.

## Command

```text
make data SEED=42
```

For smaller local runs:

```text
make data SEED=42 N_CONSUMERS=1000 N_MERCHANTS=100 OUTPUT_DIR=data/generated/stage1-small
```

## Output

Files are written under `data/generated/stage1/` by default:

```text
transactions.parquet
labels.parquet
parties.parquet
devices.parquet
merchants.parquet
mandates.parquet
disputes.parquet
graph_edges.parquet
manifest.json
validation_report.json
```

Mandates, disputes and graph edges are written as empty schema-valid tables in
Stage 1. Later stages will populate them.

## Generation assumptions

The generator uses `src/generators/population.py` as input and writes only the
existing schema classes. Consumer transaction counts depend on income persona.
P2M vs P2P selection is biased by each party's `organic_spend_ratio`, while P2P
counterparty pools are sized from `distinct_counterparties_30d`. Merchant
selection uses the population's internal long-tail volume weights.

Device selection mostly uses known active devices, with rare legitimate unknown
device cases. Device first/last seen and retirement timestamps are respected.
Session, authentication, amount and decision fields are correlated with rail,
channel, first-beneficiary use and amount. The generator includes ordinary
declines and unusual-but-legitimate behaviour so the baseline is not perfectly
clean.

The target party aggregates are intentionally approximate in Stage 1. Exact
rolling realised ratios belong in the later validation/reporting layer after
transactions exist.

## Reproducibility

All IDs and samples come from seeded NumPy generators plus the existing
deterministic UUID helper. The manifest intentionally avoids wall-clock creation
timestamps so repeated runs with the same seed and scale remain logically
deterministic.

## Validation

`src/validation/legitimate.py` validates schema conformance, transaction ID
uniqueness, foreign keys, timestamp bounds, amount validity, authentication
consistency, device-known consistency and label separation. It also writes
summary statistics used by the CLI output and `validation_report.json`.
