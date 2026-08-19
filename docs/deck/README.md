# Walkthrough deck

`chakravyuh-walkthrough.pptx` is the mandatory "solution walkthrough" submission artifact
(issues.md I13): attacks found, generation method, detection results, real-world
feasibility. It's generated, not hand-authored, and committed to the repo so it exists
as a concrete file for submission -- regenerate after any of the source docs change:

```
uv run python docs/deck/build_deck.py
```

Every number and claim in it is sourced from a real project doc (see the SOURCE comment
above each slide's content in `build_deck.py`, and the speaker notes in the .pptx itself)
-- `docs/model-choice.md`, `docs/closed-loop.md`, `docs/attack-catalogue.md`,
`docs/research/`, `issues.md`. Nothing is invented for the slide. Two placeholders remain
deliberately unfilled rather than fabricated: team name/contact (title and closing
slides) and a prototype screenshot (needs a trained model + a display to capture).
