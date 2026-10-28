"""Hợp đồng vocab Q và hash: Q ở cuối, hash canonical, artifact cũ không có hash."""

from __future__ import annotations

import pytest

from vifasttts.frontend.lexicon import strict_warnings
from vifasttts.frontend.syllable import parse_syllable
from vifasttts.frontend.vocab import (
    VOCAB_HASH,
    VOCAB_VERSION,
    ComponentVocabs,
    verify_vocab_hash,
    vocab_hash,
    vocab_payload,
)


def test_q_is_last_onset_and_old_ids_stay():
    vocabs = ComponentVocabs.default()
    assert VOCAB_VERSION == "vi-q25-v1"
    assert len(VOCAB_HASH) == 64
    assert VOCAB_HASH == vocab_hash()
    assert vocab_payload()["onset"][-1] == "Q"
    assert len(vocabs.onset) == 25
    assert vocabs.onset["Q"] == 24
    assert vocabs.onset["K"] == 18
    assert vocabs.onset["NONE"] == 0


def test_vocab_hash_guard_rejects_mismatch():
    verify_vocab_hash({}, "legacy")
    verify_vocab_hash({"vocab_hash": VOCAB_HASH}, "current")
    with pytest.raises(ValueError, match="vocab_hash"):
        verify_vocab_hash({"vocab_hash": "bad"}, "wrong")


def test_quoc_is_q_but_cuoc_is_k():
    quoc = parse_syllable("quốc").abstract
    cuoc = parse_syllable("cuốc").abstract
    assert (quoc.onset, quoc.medial, quoc.nucleus) == ("Q", "NONE", "UÔ")
    assert (cuoc.onset, cuoc.medial, cuoc.nucleus) == ("K", "NONE", "UÔ")


def test_qu_with_medial_is_q_w():
    for word, nucleus in (("qua", "A"), ("quất", "Â"), ("quyển", "IÊ"), ("quơ", "Ơ")):
        abstract = parse_syllable(word).abstract
        assert (abstract.onset, abstract.medial, abstract.nucleus) == ("Q", "W", nucleus)


def test_labial_w_allowlist():
    for word in ("buýt", "voan", "boa"):
        assert "labial-w" not in strict_warnings(parse_syllable(word))
    assert "labial-w" in strict_warnings(parse_syllable("bóa"))
