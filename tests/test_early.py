from livetranslate.config import Settings
from livetranslate.pipeline import Pipeline
from livetranslate.soniox_client import Batch, Token
from livetranslate.speech_planner import EarlyCommitter
from livetranslate.transcript import TranscriptRecorder
from livetranslate.tts import ListSpeaker


def T(text, final, status="translation"):
    return Token(text=text, is_final=final, status=status)


class FakeDisplay:
    def __init__(self):
        self.shown = []

    def update_partial(self, o, t):
        pass

    def show(self, utt):
        self.shown.append(utt)


def make(early):
    s = Settings(api_key="k", target="en", early=early, early_agree=2)
    sp = ListSpeaker()
    pl = Pipeline(s, sp, TranscriptRecorder("/tmp/lt_test", "en", enabled=False), FakeDisplay())
    return pl, sp


def test_committer_waits_for_agreement_and_never_speaks_last_word():
    e = EarlyCommitter(agree=2)
    assert e.on_nonfinal(" Hello wor") == ""            # only one sample
    assert e.on_nonfinal(" Hello world and") == " Hello"  # stable prefix " Hello wor", minus unfinished word
    assert e.on_nonfinal(" Hello world and more") == " world"


def test_early_mode_does_not_double_speak():
    pl, sp = make(early=True)
    # two responses with the same non-final text -> early speech of the stable words
    pl.on_batch(Batch(tokens=[T(" Hello", False), T(" big", False), T(" world", False)]))
    pl.on_batch(Batch(tokens=[T(" Hello", False), T(" big", False), T(" world", False)]))
    pl._speak(pl.planner.flush())          # (idle timer would do this in real life)
    assert sp.phrases == ["Hello big"]
    # now the same text arrives as FINAL, then the endpoint
    pl.on_batch(Batch(tokens=[T(" Hello", True), T(" big", True), T(" world", True), T("<end>", True, "none")]))
    pl._speak(pl.planner.flush())
    all_spoken = " ".join(sp.phrases)
    assert all_spoken.count("Hello") == 1
    assert all_spoken.count("big") == 1
    assert all_spoken.count("world") == 1


def test_normal_mode_speaks_only_final_translation():
    pl, sp = make(early=False)
    pl.on_batch(Batch(tokens=[T(" Hello", False), T(" there", False)]))
    assert sp.phrases == []
    pl.on_batch(Batch(tokens=[T(" Hello", True), T(" there", True), T(".", True), Token("<end>", True, "none")]))
    assert sp.phrases == ["Hello there."]


def test_own_language_original_tokens_are_not_spoken():
    pl, sp = make(early=False)
    pl.on_batch(Batch(tokens=[Token("How are you?", True, "none"), Token("<end>", True, "none")]))
    pl._speak(pl.planner.flush())
    assert sp.phrases == []
