import unittest
from src.core.winner_detector import jaro_winkler_similarity, are_names_similar, LoneWolfWinnerDetector
from PIL import Image

class TestWinnerDetector(unittest.TestCase):
    def test_jaro_winkler_similarity(self):
        # Identical
        self.assertAlmostEqual(jaro_winkler_similarity("ROLEX", "ROLEX"), 1.0)
        # Empty
        self.assertEqual(jaro_winkler_similarity("", "ROLEX"), 0.0)
        # Close match
        score = jaro_winkler_similarity("MARTHA", "MARHTA")
        self.assertGreater(score, 0.9)

    def test_are_names_similar_dedup(self):
        # SAAAAD vs SAD collapsing
        self.assertTrue(are_names_similar("SAAAAD", "SAD"))
        self.assertTrue(are_names_similar("꧁༺SAAAAD༻꧂", "SAD"))

    def test_are_names_similar_substring(self):
        # OLEX in ROLEX (80% coverage)
        self.assertTrue(are_names_similar("OLEX", "ROLEX"))

    def test_are_names_similar_different(self):
        # Different names
        self.assertFalse(are_names_similar("mimvai", "shamimvai"))
        self.assertFalse(are_names_similar("ALOK", "HAYATO"))

    def test_winner_detector_mock(self):
        class MockPaddleOCR:
            def ocr(self, img_arr, cls=False):
                # Mock OCR returning appropriate text based on slot shape/size
                return [[
                    [[[10, 10], [100, 10], [100, 30], [10, 30]], ("SAD", 0.95)]
                ]]

        class MockLWDetector(LoneWolfWinnerDetector):
            def extract_winners_and_losers(self, image):
                return {
                    "top1": ["SAD", "ROLEX"],
                    "top2": ["NOOB", "BOT"],
                    "top1_count": 2,
                    "top2_count": 2,
                    "active_slots": 4
                }

        detector = MockLWDetector()
        test_img = Image.new("RGB", (1280, 720), color=(30, 30, 30))

        # Standard Lone Wolf
        res_normal = detector.determine_match_winners(test_img, game_mode="Lone Wolf")
        self.assertEqual(res_normal["top1"], ["SAD", "ROLEX"])
        self.assertEqual(res_normal["top2"], ["NOOB", "BOT"])
        self.assertEqual(res_normal["winners"], ["SAD", "ROLEX"])
        self.assertFalse(res_normal["is_ltw"])

        # Lose To Win (LTW)
        res_ltw = detector.determine_match_winners(test_img, game_mode="Lose To Win")
        self.assertEqual(res_ltw["winners"], ["NOOB", "BOT"])
        self.assertTrue(res_ltw["is_ltw"])

if __name__ == "__main__":
    unittest.main()
