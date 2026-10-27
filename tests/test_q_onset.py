"""Hợp đồng vocab Q: Q ở cuối, ID cũ giữ nguyên, checkpoint cũ bị từ chối rõ ràng."""
from __future__ import annotations

import pytest

from vifasttts.frontend.lexicon import strict_warnings
from vifasttts.frontend.syllable import parse_syllable
from vifasttts.frontend.vocab import ONSET_HAS_Q, ComponentVocabs
from vifasttts.models.factory import require_onset_has_q


def test_q_is_last_onset_and_old_ids_stay():
    vocabs = ComponentVocabs.default()
    assert ONSET_HAS_Q is True
    assert len(vocabs.onset) == 25
    assert vocabs.onset["Q"] == 24
    assert vocabs.onset["K"] == 18
    assert vocabs.onset["NONE"] == 0


def test_quoc_is_q_but_cuoc_is_k():
    quoc = parse_syllable("quốc").abstract
    cuoc = parse_syllable("cuốc").abstract
    assert (quoc.onset, quoc.medial, quoc.nucleus) == ("Q", "NONE", "UÔ")
    assert (cuoc.onset, cuoc.medial, cuoc.nucleus) == ("K", "NONE", "UÔ")


def test_qu_with_medial_is_q_w():
    for word, nucleus in (("qua", "A"), ("quất", "Â"), ("quyển", "IÊ"), ("quơ", "Ơ")):
        abstract = parse_syllable(word).abstract
        assert (abstract.onset, abstract.medial, abstract.nucleus) == ("Q", "W", nucleus)


def test_require_onset_has_q_rejects_legacy_checkpoint():
    with pytest.raises(ValueError, match="onset_has_q"):
        require_onset_has_q({}, "old.pt")
    require_onset_has_q({"onset_has_q": True}, "new.pt")


def test_labial_w_allowlist():
    for word in ("buýt", "voan", "boa"):
        assert "labial-w" not in strict_warnings(parse_syllable(word))
    assert "labial-w" in strict_warnings(parse_syllable("bóa"))
