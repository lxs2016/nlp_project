---
title: StoryWeaver
sdk: gradio
sdk_version: "4.0.0"
app_file: app.py
python_version: "3.10"
pinned: false
---

## StoryWeaver (Hugging Face Spaces)

This repository contains **StoryWeaver**, an interactive fiction demo built with **Gradio**.

### Run locally

```bash
python app_gradio.py
```

### Deploy on Hugging Face Spaces

- Create a new Space with **SDK = Gradio**
- Push this repo to the Space
- In Space **Settings → Variables and secrets**, set:
  - `OPENAI_API_KEY`
  - `OPENAI_API_BASE`
  - `OPENAI_MODEL`

Notes:
- Do **not** commit `.env` (already ignored by `.gitignore`).
- The Space entrypoint is `app.py` (exports `demo`).
