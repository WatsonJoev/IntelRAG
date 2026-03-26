from core.complexity_classifier import classify, Tier


def test_simple_short_what_is():
    tier, model = classify("What is the SLA?", turn_count=0)
    assert tier == Tier.SIMPLE


def test_complex_compare_keyword():
    tier, model = classify("Compare the pricing models across all three proposals", turn_count=0)
    assert tier == Tier.COMPLEX


def test_moderate_summarize_keyword():
    tier, model = classify("Summarize the key findings of the Q3 report", turn_count=0)
    assert tier == Tier.MODERATE


def test_deep_conversation_escalates():
    tier, _ = classify("What else?", turn_count=5)
    assert tier == Tier.COMPLEX


def test_long_query_defaults_complex():
    long = " ".join(["word"] * 50)
    tier, _ = classify(long, turn_count=0)
    assert tier == Tier.COMPLEX


def test_model_id_matches_tier():
    from config.settings import get_settings
    s = get_settings()
    _, model = classify("Who is the author?", turn_count=0)
    assert model == s.tier_1_model
