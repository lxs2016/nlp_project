"""Planner: state + intent -> plan_text, suggested_choices (2-4) for Generator."""
from __future__ import annotations

from typing import Any

# Intent -> short plan hint + default choice templates (Generator can expand)
_PLAN_TEMPLATES = {
    "continue": (
        "推进剧情，根据当前状态与玩家选择发展情节，保持与世界观一致。",
        ["探索当前地点", "与在场角色对话", "做出关键抉择", "前往其他地点"],
    ),
    "start": (
        "开场：建立场景与氛围，介绍当前地点与可选行动。",
        ["开始探索", "与某人交谈", "查看周围"],
    ),
    "fail_forward": (
        "失败但推进：选择带来不利结果，但故事继续，给出新的选项。",
        ["尝试其他方式", "接受后果并继续", "寻求帮助"],
    ),
    "meta_help": (
        "回应玩家对状态/帮助的请求，简要总结当前状态。",
        ["继续游戏", "查看状态"],
    ),
    "end": (
        "收尾：本段作为结局或章节结束，可留悬念。",
        ["结束", "回顾"],
    ),
    "init": (
        "初始化场景与角色，为后续剧情铺垫。",
        ["开始", "了解情况"],
    ),
}


def plan(
    state_summary: str,
    intent: str,
    retrieved_context: str = "",
    main_conflict: str = "",
) -> tuple[str, list[str]]:
    """
    Return (plan_text, suggested_choices).
    suggested_choices: 2-4 semantic option directions for the generator.
    """
    plan_text, choices = _PLAN_TEMPLATES.get(
        intent, _PLAN_TEMPLATES["continue"]
    )
    if main_conflict:
        plan_text = f"{plan_text} 主线冲突：{main_conflict[:100]}"
    if retrieved_context:
        plan_text = f"{plan_text}\n相关前情：{retrieved_context[:200]}"
    return plan_text, choices[:4]
