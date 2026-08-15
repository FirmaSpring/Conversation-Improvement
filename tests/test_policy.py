from conversation_improvement.policy import ExpressionPolicy, SessionState


def test_explicit_image_request_is_always_allowed():
    policy = ExpressionPolicy(probability=0.0)
    result = policy.decide("我想看看你今天的自拍", SessionState(turn=1))
    assert result.allowed is True
    assert result.kind == "explicit"


def test_serious_context_never_allows_automatic_expression():
    policy = ExpressionPolicy(probability=1.0, cooldown_turns=0)
    result = policy.decide("这个报错让我很难受，帮我认真调试", SessionState(turn=20))
    assert result.allowed is False
    assert result.reason == "sensitive_context"


def test_automatic_expression_obeys_cooldown_and_session_limit():
    policy = ExpressionPolicy(probability=1.0, cooldown_turns=8, max_per_session=2)
    assert policy.decide("哈哈太有意思了", SessionState(turn=10, last_auto_turn=5)).reason == "cooldown"
    assert policy.decide("哈哈太有意思了", SessionState(turn=20, automatic_count=2)).reason == "session_limit"
    assert policy.decide("哈哈太有意思了", SessionState(turn=20, last_auto_turn=5)).allowed is True


def test_probability_gate_is_stable_for_same_turn():
    policy = ExpressionPolicy(probability=0.25)
    state = SessionState(session_id="abc", turn=12)
    assert policy.decide("今天真开心", state) == policy.decide("今天真开心", state)


def test_ordinary_chat_can_trigger_without_playful_keywords():
    policy = ExpressionPolicy(probability=1.0)
    result = policy.decide("姐姐你今天在做什么", SessionState(turn=2))
    assert result.allowed is True
    assert result.reason == "casual_moment"


def test_fourth_eligible_casual_turn_is_guaranteed():
    policy = ExpressionPolicy(probability=0.0, playful_probability=0.0, force_after_casual_turns=4)
    result = policy.decide("今天吃什么呀", SessionState(turn=8, casual_streak=3))
    assert result.allowed is True
    assert result.reason == "casual_guarantee"


def test_professional_task_remains_blocked():
    policy = ExpressionPolicy(probability=1.0, playful_probability=1.0)
    result = policy.decide("帮我重构这个项目并运行测试", SessionState(turn=8, casual_streak=9))
    assert result.allowed is False
    assert result.reason == "sensitive_context"


def test_affectionate_actions_are_eligible_for_automatic_reaction():
    policy = ExpressionPolicy(probability=0.0, playful_probability=1.0)
    for message in ("给姐姐抱抱", "亲亲姐姐", "姐姐冷不冷，哈气暖暖"):
        result = policy.decide(message, SessionState(turn=3))
        assert result.allowed is True
        assert result.reason == "affectionate_action"