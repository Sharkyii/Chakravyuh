# Stage 2 graph and dataset harness

Stage 2 reads a Stage 1 legitimate dataset and creates analysis-ready graph and
dataset artifacts. It does not add attacks, ML models or model features.

## Workflow

```text
make data SEED=42 N_CONSUMERS=1000 N_MERCHANTS=100 OUTPUT_DIR=data/generated/stage1-small
make graph OUTPUT_DIR=data/generated/stage1-small STAGE2_OUTPUT_DIR=data/generated/stage2-small
```

If `make` is unavailable on Windows, use the direct CLI:

```text
uv run python -m src.dataset.stage2 --input-dir data/generated/stage1-small --output-dir data/generated/stage2-small
```

## Graph construction

`src/graph/builder.py` derives `graph_edges` from transaction rows only. Each
directed edge is `payer_id -> payee_id`, which also covers payer-to-merchant
relationships because merchant transactions use the merchant party as payee.

For each edge the builder computes:

```text
edge_count
edge_value_total
mean_inter_arrival_s
src_out_degree
dst_in_degree
is_two_hop_passthrough
```

`is_two_hop_passthrough` is marked when the destination later pays a different
party inside the same graph window. This is a window-level offline artifact, not
a pre-transaction online feature.

## Temporal safety

Temporal splitting is timestamp-based, never random. The default 12-week window
is split as:

```text
train: 60%
validation: 20%
test: 20%
```

Split boundaries are configurable through `TemporalSplitConfig`. The full
`graph_edges.parquet` artifact covers the full dataset window. For training,
later ML code should build graph features using the split-specific windows or a
per-transaction historical graph, not the full-window graph.

## Leakage checks

`src/dataset/leakage.py` checks:

```text
duplicate transaction IDs
duplicate labels
labels exactly matching transactions
duplicate IDs across temporal splits
rows crossing split boundaries
label-only columns appearing in transaction features
invalid party, merchant or device references
legitimate-only label integrity
invalid graph edge references or graph windows
```

## Output

Stage 2 writes all original Stage 1 tables plus populated `graph_edges.parquet`,
a deterministic `manifest.json`, and a `validation_report.json` with graph,
split, foreign-key, schema and leakage summaries.

Later attack generators can consume the Stage 2 dataset as the legitimate
baseline and append or modify transactions, labels and graph relationships in a
controlled Stage 3 pipeline.
