import unittest
from pathlib import Path

from calllog import analyze
from calllog.models import ActionItem
from calllog.parsers import parse_text_file

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
CALL = SAMPLES / "통화 녹음 김지훈_261117_210000.txt"


class KeywordTest(unittest.TestCase):
    def setUp(self):
        self.text = parse_text_file(CALL).full_text

    def test_keywords_have_no_josa_or_filler(self):
        kws = analyze.keywords(self.text, 10)
        self.assertTrue(kws)
        for word in kws:
            self.assertNotIn(word, analyze.STOPWORDS)
            self.assertFalse(analyze._VERB_TAIL.search(word), word)
        joined = " ".join(kws)
        for bad in ("그리고", "합니다", "그럼", "드릴게요", "수정은"):
            self.assertNotIn(bad, joined)

    def test_domain_words_are_picked(self):
        kws = analyze.keywords(self.text, 10)
        self.assertTrue({"시안", "납품", "계약금"} & set(kws))

    def test_empty_text(self):
        self.assertEqual(analyze.keywords("", 10), [])


class AmountDateTest(unittest.TestCase):
    def setUp(self):
        self.text = parse_text_file(CALL).full_text

    def test_amounts(self):
        amounts = analyze.amounts_in(self.text)
        self.assertIn("350만 원", amounts)
        self.assertIn("175만 원", amounts)

    def test_dates(self):
        dates = analyze.dates_in(self.text)
        self.assertIn("11월 20일", dates)
        self.assertTrue(any("내일" in d for d in dates))


class SummaryTest(unittest.TestCase):
    def setUp(self):
        parsed = parse_text_file(CALL)
        self.segments = parsed.segments
        self.kws = analyze.keywords(parsed.full_text, 10)

    def test_summary_contains_key_terms(self):
        summary = analyze.summarize(self.segments, 5, self.kws)
        self.assertTrue(1 <= len(summary) <= 5)
        joined = " ".join(summary)
        self.assertIn("11월 20일", joined)
        self.assertIn("시안", joined)

    def test_summary_is_in_original_order(self):
        summary = analyze.summarize(self.segments, 5, self.kws)
        orders = []
        for text in summary:
            orders.append(next(i for i, s in enumerate(analyze.sentences_from(self.segments)) if s.text == text))
        self.assertEqual(orders, sorted(orders))

    def test_limit_is_respected(self):
        self.assertLessEqual(len(analyze.summarize(self.segments, 2, self.kws)), 2)

    def test_empty(self):
        self.assertEqual(analyze.summarize([], 5), [])


class ActionTest(unittest.TestCase):
    def setUp(self):
        parsed = parse_text_file(CALL)
        self.segments = parsed.segments
        self.speakers = parsed.speakers

    def test_actions_found(self):
        actions = analyze.extract_actions(self.segments, 8, self.speakers)
        self.assertTrue(actions)
        texts = " ".join(a.text for a in actions)
        self.assertIn("발주서", texts)
        self.assertIn("보내", texts)

    def test_no_pleasantry_items(self):
        actions = analyze.extract_actions(self.segments, 8, self.speakers)
        for item in actions:
            self.assertNotIn("잘 부탁드립니다", item.text)
            self.assertNotIn("수고하셨습니다", item.text)

    def test_owner_and_due(self):
        actions = analyze.extract_actions(self.segments, 8, self.speakers)
        owned = [a for a in actions if a.owner]
        self.assertTrue(owned, "약속한 문장에는 발화자가 담당으로 붙어야 한다")
        self.assertTrue(any(a.due for a in actions))

    def test_limit(self):
        self.assertLessEqual(len(analyze.extract_actions(self.segments, 3, self.speakers)), 3)

    def test_sentence_split(self):
        parts = analyze.split_sentences("안녕하세요. 오늘은 11월 20일까지 납품 가능할까요? 네 알겠습니다.")
        self.assertEqual(len(parts), 3)


if __name__ == "__main__":
    unittest.main()
