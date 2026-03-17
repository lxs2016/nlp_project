# StoryEngine raw data

- **Source**: [SatorTenet/storyengine-dataset](https://huggingface.co/datasets/SatorTenet/storyengine-dataset) (Hugging Face)
- **Total rows**: 3140
- **Format**: One JSON object per line (JSONL). Each object has `messages` (list of {role, content}) and `meta` (type, genre, polti, etc.).
- **License**: Apache 2.0

## meta.type distribution

| type | count |
|------|-------|
| scene_continuation | 2000 |
| genre_opening | 360 |
| fail_forward | 300 |
| command_response | 200 |
| session_end | 200 |
| init_sequence | 80 |
