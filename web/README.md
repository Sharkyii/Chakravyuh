# Web prototype

```
uv run streamlit run web/app.py
```

Three tabs:

- **Live scoring** — pick a scenario (or hand-tune the fields that matter: coercion
  signals, beneficiary age, graph edge count) and run it through the real Stage 6
  pipeline (`stage5.inference.pipeline.analyze_transaction`) — fraud score, predicted
  attack family, contributing signals, analyst narrative. Needs a trained model in
  `stage5/models/` (see the in-app instructions if one isn't there yet).
- **Closed loop** — the I6/I7/I17 diagnosis, live feature importances if a model is
  saved, and what the next `adversarial_evasion` generation will target
  (`stage5/training/build_adaptive_attack_config.py`, live). Full writeup:
  `docs/closed-loop.md`.
- **Attack catalogue** — the 13 generators from `docs/attack-catalogue.md`'s merge map.

`web/scenarios.py` holds the hand-built example transactions the scenario picker uses —
illustrative single rows matching each family's documented data signature, not generated
data.
