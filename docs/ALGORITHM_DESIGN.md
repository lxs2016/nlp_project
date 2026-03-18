# Algorithm Design — Module I/O and Data Paths

Brief design document for the report "Algorithm design" section. All paths relative to project root.

## Data dependencies (from Data preparation)

| Module | Data path | Usage |
|--------|-----------|--------|
| IntentRecognizer | `data/annotations/intent_train.jsonl`, `intent_val.jsonl`, `intent_test.jsonl` | Training and evaluation; `input_text` -> `intent_label` |
| StateAndMemory | `data/world_bible/world_main.yaml` | GameState init, rules_forbidden, entities |
| MemoryRetriever | Optional: `data/plot_units/storyengine_units.jsonl` | Optional static index; runtime memory from StateAndMemory |
| ConsistencyChecker | `data/world_bible/world_main.yaml`; optional `data/annotations/consistency_annotations.jsonl` | Rules from WorldBible; optional training |
| Generator / Planner | `data/world_bible/world_main.yaml` | Prompt injection; optional few-shot from plot_units |

## Module I/O

- **IntentRecognizer**  
  - In: `text: str` (player input).  
  - Out: `(intent_label: str, confidence: float)`.  
  - Model path: `models/intent/` (after training).

- **StateAndMemory (game/state.py, game/memory.py)**  
  - In: WorldBible; generator `state_updates`.  
  - Out: `state.to_prompt_summary()`, `state.state_summary()`, memory entries for retrieval.

- **MemoryRetriever (models/retriever.py)**  
  - In: `Memory`, `state_summary`, `intent`, `k`, `recent_n`.  
  - Out: `retrieved_context: str`.

- **Planner (models/planner.py)**  
  - In: `state_summary`, `intent`, `retrieved_context`, `main_conflict`.  
  - Out: `(plan_text: str, suggested_choices: List[str])`.

- **Generator (models/generator.py)**  
  - In: WorldBible, state_summary, retrieved_context, plan_text, suggested_choices, user_input.  
  - Out: `(narration: str, choices: List[str], state_updates: dict)`.

- **ConsistencyChecker (models/consistency.py)**  
  - In: `GameState`, `narration`, `state_updates`.  
  - Out: `(passed: bool, reason: str)`.

- **GameEngine.step (game/engine.py)**  
  - In: `session_id: str`, `user_input: str`.  
  - Out: `(narration: str, choices: List[str], state_summary: str, error_message: str)`.

## Single-step API contract (for System implementation)

- **Entry**: `game.engine.step(session_id, user_input)`  
- **Returns**: `(narration, choices, state_summary, error_message)`  
- **Side effects**: Per-session GameState and Memory updated; new game via `game.engine.reset_session(session_id)`.

## Hyperparameters / thresholds

- Intent: default label `continue` when no model or low confidence.
- Retriever: `k=5`, `recent_n=3` (in `step()`).
- Generator: `max_retries=2` for JSON parse; consistency retry loop 3 attempts.
- Memory: `max_entries=100` per session.
