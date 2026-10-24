from livetranslate.tts import pick_edge_voice

VOICES = [
    {"ShortName": "en-GB-SoniaNeural", "Locale": "en-GB"},
    {"ShortName": "en-US-AriaNeural", "Locale": "en-US"},
    {"ShortName": "ko-KR-SunHiNeural", "Locale": "ko-KR"},
    {"ShortName": "pt-PT-RaquelNeural", "Locale": "pt-PT"},
    {"ShortName": "pt-BR-FranciscaNeural", "Locale": "pt-BR"},
]


def test_prefers_default_locale():
    assert pick_edge_voice("en", VOICES) == "en-US-AriaNeural"
    assert pick_edge_voice("pt", VOICES) == "pt-BR-FranciscaNeural"


def test_exact_locale_and_missing():
    assert pick_edge_voice("pt-PT", VOICES) == "pt-PT-RaquelNeural"
    assert pick_edge_voice("ko", VOICES) == "ko-KR-SunHiNeural"
    assert pick_edge_voice("xx", VOICES) is None
