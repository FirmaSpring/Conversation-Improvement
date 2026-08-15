from __future__ import annotations

import hashlib
from dataclasses import dataclass


EXPLICIT_TERMS = (
    "发张图", "发图片", "生成图片", "生成一张", "画一张", "看看你", "看你",
    "自拍", "照片", "表情包", "gif", "image", "picture", "show me",
)
SENSITIVE_TERMS = (
    "报错", "错误", "调试", "代码", "考试", "作业", "学习", "难受", "痛苦",
    "生病", "隐私", "密码", "事故", "去世", "分手", "严肃", "debug", "error",
    "项目", "重构", "部署", "测试", "终端", "命令", "算法", "论文", "报告", "分析", "任务",
    "project", "refactor", "deploy", "terminal", "command", "algorithm", "report", "analysis", "task",
)
PLAYFUL_TERMS = (
    "哈哈", "开心", "好耶", "可爱", "调皮", "惊喜", "逗", "笑死", "庆祝",
    "嘿嘿", "有意思", "funny", "cute", "yay", "lol",
)
AFFECTIONATE_ACTION_TERMS = (
    "抱抱", "拥抱", "抱一下", "亲亲", "亲一口", "飞吻", "贴贴", "蹭蹭",
    "哈气", "呵气", "暖暖", "摸摸头", "摸头", "牵手", "拉手",
)


@dataclass(frozen=True)
class SessionState:
    session_id: str = "default"
    turn: int = 0
    last_auto_turn: int | None = None
    automatic_count: int = 0
    casual_streak: int = 0


@dataclass(frozen=True)
class Decision:
    allowed: bool
    kind: str
    reason: str


class ExpressionPolicy:
    def __init__(
        self,
        probability: float = 0.32,
        playful_probability: float = 0.65,
        force_after_casual_turns: int = 4,
        cooldown_turns: int = 5,
        max_per_session: int = 20,
    ):
        self.probability = min(1.0, max(0.0, probability))
        self.playful_probability = min(1.0, max(0.0, playful_probability))
        self.force_after_casual_turns = max(1, force_after_casual_turns)
        self.cooldown_turns = max(0, cooldown_turns)
        self.max_per_session = max(0, max_per_session)

    def decide(self, message: str, state: SessionState) -> Decision:
        text = message.casefold()
        if any(term in text for term in EXPLICIT_TERMS):
            return Decision(True, "explicit", "user_requested")
        if any(term in text for term in SENSITIVE_TERMS):
            return Decision(False, "none", "sensitive_context")
        if state.automatic_count >= self.max_per_session:
            return Decision(False, "none", "session_limit")
        if state.last_auto_turn is not None and state.turn - state.last_auto_turn < self.cooldown_turns:
            return Decision(False, "none", "cooldown")
        playful = any(term in text for term in PLAYFUL_TERMS)
        affectionate_action = any(term in text for term in AFFECTIONATE_ACTION_TERMS)
        if affectionate_action:
            return Decision(True, "automatic", "affectionate_action")
        if state.casual_streak + 1 >= self.force_after_casual_turns:
            return Decision(True, "automatic", "casual_guarantee")
        seed = f"{state.session_id}:{state.turn}:{text}".encode("utf-8")
        sample = int.from_bytes(hashlib.sha256(seed).digest()[:8], "big") / 2**64
        threshold = self.playful_probability if playful else self.probability
        if sample >= threshold:
            return Decision(False, "none", "probability_gate")
        return Decision(True, "automatic", "playful_moment" if playful else "casual_moment")