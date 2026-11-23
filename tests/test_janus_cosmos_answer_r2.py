"""No-download JANUS COSMOS R2 tests, including honest uncertainty gates."""
import unittest
from tools import janus_cosmos_answer_r2 as r


class JanusCosmosDirectAnswerR2Tests(unittest.TestCase):

    def test_coherent_answer_passes_structural_smoke(self):
        a = (
            "Пока мы не знаем, где находятся инопланетяне: достоверных свидетельств "
            "внеземной жизни или цивилизаций нет. "
            "Самые перспективные места поиска — подповерхностные среды Марса, "
            "океан подо льдом Европы и некоторые экзопланеты. "
            "Возможность жизни там не означает, что она уже найдена."
        )
        grade = r.evaluate_answer(a)
        self.assertEqual(grade["status"], "PASS_SOURCE_GROUNDED_SMOKE")
        self.assertTrue(grade["uncertainty_or_no_confirmed_location"])
        self.assertTrue(grade["multiple_sites"])
        self.assertFalse(grade["proves_improved_general_reasoning"])

    def test_empty_answer_is_rejected(self):
        with self.assertRaises(ValueError):
            r.evaluate_answer("")

    def test_confident_location_without_evidence_is_held(self):
        a = (
            "Инопланетяне уже существуют на планете номер семь в дальней системе. "
            "Они скрываются от Земли и присылают сообщения каждый день."
        )
        self.assertEqual(r.evaluate_answer(a)["status"], "HOLD_ANSWER_QUALITY")

    def test_nonanswer_with_no_locations_held(self):
        a = (
            "Мы не можем точно знать, где они находятся. "
            "И мы не можем знать этого, потому что не можем знать, где они."
        )
        self.assertEqual(r.evaluate_answer(a)["status"], "HOLD_ANSWER_QUALITY")

    def test_grounded_sources_frozen(self):
        self.assertEqual(r.MODEL_ID, "Qwen/Qwen2.5-1.5B-Instruct")
        self.assertEqual(r.SCHEMA, "janus.cosmos.direct_answer_r2.v1")
        self.assertIn("Где вообще инопланетяне", r.PROMPT)

    def test_preserves_uncertainty_without_claiming_detection(self):
        a = (
            "Нам неизвестно местонахождение разумных инопланетян. "
            "Для поиска жизни изучают Марс и экзопланеты, однако это кандидаты, "
            "а не доказанные источники сигналов."
        )
        self.assertEqual(r.evaluate_answer(a)["status"], "PASS_SOURCE_GROUNDED_SMOKE")


if __name__ == "__main__":
    unittest.main()
