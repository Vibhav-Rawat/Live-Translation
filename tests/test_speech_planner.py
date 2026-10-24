from livetranslate.speech_planner import SpeechPlanner


def feed_all(planner, pieces):
    out = []
    for p in pieces:
        out += planner.feed(p)
    return out


def test_sentence_end_flushes_and_joins_word_pieces():
    p = SpeechPlanner()
    assert feed_all(p, ["Hel", "lo", " wor", "ld", "."]) == ["Hello world."]


def test_short_clause_waits_but_long_clause_flushes():
    p = SpeechPlanner(min_clause_words=3)
    # "Well," is only one word: keep going
    assert feed_all(p, ["Well", ","]) == []
    assert feed_all(p, [" I", " think", " so", ","]) == ["Well, I think so,"]


def test_word_limit_flushes_before_next_word():
    p = SpeechPlanner(max_words=4)
    out = feed_all(p, ["one", " two", " three", " four", " five", " six"])
    assert out == ["one two three four"]
    assert p.flush() == ["five six"]


def test_decimal_number_is_not_split():
    p = SpeechPlanner()
    out = feed_all(p, ["It", " costs", " 3", ".", "5", " dollars", "."])
    assert out == ["It costs 3.5 dollars."]


def test_number_then_sentence_end_still_flushes():
    p = SpeechPlanner()
    out = feed_all(p, ["I", " have", " 3", ".", " Next"])
    assert out == ["I have 3."]
    assert p.flush() == ["Next"]


def test_end_token_flushes():
    p = SpeechPlanner()
    assert feed_all(p, ["Hi", " there"]) == []
    assert p.feed("<end>") == ["Hi there"]


def test_idle_flush_uses_clock():
    now = [0.0]
    p = SpeechPlanner(idle_ms=500, clock=lambda: now[0])
    p.feed("Hello")
    now[0] = 0.3
    assert p.poll() == []
    now[0] = 0.6
    assert p.poll() == ["Hello"]
    assert p.poll() == []


def test_cjk_flushes_by_length():
    p = SpeechPlanner(cjk_chars=6)
    out = feed_all(p, ["\u3053\u3093", "\u306b\u3061", "\u306f\u4e16", "\u754c"])
    assert out == ["\u3053\u3093\u306b\u3061\u306f\u4e16"]


def test_closing_quote_after_period():
    p = SpeechPlanner()
    assert feed_all(p, ["He", " said", " go", ".", '"']) == ["He said go."]
    assert p.flush() == []  # the lone closing quote is not spoken
