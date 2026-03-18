## LLM-as-judge prompt template (optional)

### System
You are a strict evaluator of interactive fiction quality. You score coherence with WorldBible and previous context.
Return **only JSON** with the schema specified.

### User
WorldBible (summary):
{WORLD_BIBLE_SUMMARY}

Recent context (last N turns):
{RECENT_CONTEXT}

Gold expected narration summary (for this step):
{EXPECTED_SUMMARY}

System narration (this step):
{SYSTEM_NARRATION}

Please output JSON:
{
  "score": 1-5,
  "violated_rule_type": "none|world_setting|timeline|character|location|item|forbidden_rule|other",
  "rationale": "short reason"
}

