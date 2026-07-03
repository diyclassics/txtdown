"""Tests for direct-speech quote validation (unmatched_quote, quote_style_mismatch)."""

from txtdown import parse as _parse


def parse(source):
    return _parse(source, strict=False)


def kinds(doc):
    return [i.kind for i in doc.validate()]


class TestQuotePairing:
    def test_balanced_double_quotes_clean(self):
        doc = parse(
            "--- 1\n"
            'haec secum: "Mene incepto desistere victam,\n'
            'nec posse Italia Teucrorum avertere regem?"\n'
            "Talia flammato secum dea corde volutans\n"
        )
        assert doc.validate() == []

    def test_speech_spanning_many_lines_clean(self):
        doc = parse(
            "--- 1\n"
            '"Aeole, namque tibi divom pater atque hominum rex\n'
            "et mulcere dedit fluctus et tollere vento,\n"
            "gens inimica mihi Tyrrhenum navigat aequor,\n"
            'exigat, et pulchra faciat te prole parentem."\n'
        )
        assert doc.validate() == []

    def test_unclosed_quote_is_error(self):
        doc = parse(
            "--- 1\n"
            'haec secum: "Mene incepto desistere victam,\n'
            "nec posse Italia Teucrorum avertere regem?\n"
        )
        issues = doc.validate()
        assert kinds(doc) == ["unmatched_quote"]
        assert issues[0].severity == "error"
        assert "line 1" in issues[0].message
        assert issues[0].label == "1.1"
        assert not doc.is_valid

    def test_close_only_char_without_open_is_error(self):
        doc = parse(
            "--- 1\n"
            "narration without any opening»\n"
        )
        assert kinds(doc) == ["unmatched_quote"]

    def test_asymmetric_pair_must_match(self):
        doc = parse(
            "--- 1\n"
            "tum ille dixit: «speech here»\n"
        )
        assert doc.validate() == []

    def test_guillemet_left_open_is_error(self):
        doc = parse(
            "--- 1\n"
            "tum ille dixit: «speech here\n"
            "et cetera narratio.\n"
        )
        assert kinds(doc) == ["unmatched_quote"]


class TestQuoteStyleConsistency:
    def test_single_style_many_speeches_clean(self):
        doc = parse(
            "--- 1\n"
            'prior inquit: "prima oratio."\n'
            'tum alter: "secunda oratio,\n'
            'quae in altero versu desinit."\n'
        )
        assert doc.validate() == []

    def test_mixed_styles_is_warning(self):
        # Warning, not error: quoted formulae ('uti rogas') are a different
        # function from direct speech and may legitimately use another style.
        doc = parse(
            "--- 1\n"
            'prior inquit: "prima oratio."\n'
            "tum alter: 'secunda oratio.'\n"
        )
        issues = [i for i in doc.validate() if i.kind == "quote_style_mismatch"]
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert '"' in issues[0].message and "'" in issues[0].message
        assert doc.is_valid

    def test_no_speech_at_all_clean(self):
        doc = parse(
            "--- 1\n"
            "Arma virumque cano, Troiae qui primus ab oris\n"
            "Italiam, fato profugus, Laviniaque venit\n"
        )
        assert doc.validate() == []


class TestQuoteEdgeCases:
    def test_nested_quotes_pass_through(self):
        # Single-depth validation: nested '…' inside "…" is not examined.
        # (Adapted from the normalized Aeneid 5: Cassandra's words quoted
        # within a speech.)
        doc = parse(
            "--- 1\n"
            'nam mihi Cassandrae per somnum vatis imago\n'
            "ardentis dare visa faces: \"hic quaerite Troiam;\n"
            "hic domus est' inquit 'vobis.\" iam tempus agi res,\n"
        )
        # outer "…" closes; inner '…' ignored while the outer span is open
        assert kinds(doc) == []

    def test_word_internal_apostrophe_is_not_a_quote(self):
        doc = parse(
            "--- 1\n"
            "narration with a mid'word apostrophe stays narration\n"
        )
        assert doc.validate() == []

    def test_typographic_apostrophe_not_flagged_as_stray_closer(self):
        doc = parse(
            "--- 1\n"
            "the poet’s line remains clean narration\n"
        )
        assert doc.validate() == []

    def test_speaker_lines_excluded(self):
        # @Speaker: dialogue markup is a different mechanism; an unbalanced
        # quote inside it is not inline narrative speech.
        doc = parse(
            "--- 1\n"
            '@Menaechmus: unbalanced " here\n'
        )
        assert doc.validate() == []

    def test_cross_source_quote_lines_excluded(self):
        doc = parse(
            "--- 1\n"
            '> verbatim quotation with unbalanced " mark\n'
            "normal narration follows.\n"
        )
        assert doc.validate() == []

    def test_close_directly_after_colon_is_a_close(self):
        # Lucan 7: "uictoria nobis plena, uiri:" dixit "superest…" — the
        # quote right after the colon closes the span (an introducer colon
        # always has whitespace before the quote).
        doc = parse(
            "--- 1\n"
            'in praedam ducendus erat. "uictoria nobis\n'
            'plena, uiri:" dixit "superest pro sanguine merces,\n'
            'quam monstrare meum est."\n'
        )
        assert doc.validate() == []

    def test_resumption_quote_is_caught(self):
        # Traditional typography re-opens a multi-paragraph speech with a
        # quote at each paragraph without closing the previous one. Blind
        # open/close toggling would absorb this silently; the context check
        # catches it.
        doc = parse(
            "--- 1\n"
            'tum Venus: "Haud equidem tali me dignor honore;\n'
            "ambages; sed summa sequar fastigia rerum.\n"
            '"Huic coniunx Sychaeus erat, ditissimus agri\n'
            'Europa atque Asia pulsus."\n'
        )
        issues = [i for i in doc.validate() if i.kind == "unmatched_quote"]
        assert len(issues) == 1
        assert "resumption" in issues[0].message
        assert issues[0].label == "1.3"

    def test_closing_shaped_quote_with_nothing_open_is_caught(self):
        doc = parse(
            "--- 1\n"
            'plain narration ends oddly" and continues\n'
        )
        issues = doc.validate()
        assert kinds(doc) == ["unmatched_quote"]
        assert issues[0].severity == "error"

    def test_stray_single_closer_is_warning_for_elision(self):
        # satin' = satisne elided (Livy 30.29) — indistinguishable from a
        # closing quote, so it warns rather than errors.
        doc = parse(
            "--- 1\n"
            "percunctatusque, satin' per commodum omnia explorassent.\n"
        )
        issues = doc.validate()
        assert kinds(doc) == ["unmatched_quote"]
        assert issues[0].severity == "warning"
        assert doc.is_valid

    def test_multiple_speeches_last_unclosed_reports_its_own_line(self):
        doc = parse(
            "--- 1\n"
            'tum prior: "clausa oratio."\n'
            'tum alter: "aperta oratio sine fine\n'
        )
        issues = doc.validate()
        assert kinds(doc) == ["unmatched_quote"]
        assert issues[0].label == "1.2"
