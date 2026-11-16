"""Offline contract tests for JANUS Reasoner R1; no model downloads or API calls."""
import json
import unittest
from tools import janus_reasoner_r1 as r


def good():
    return {
        "hypothesis": "undetermined", "confidence": "moderate",
        "evidence_for": [
            "Трагедия Роберта Портера объясняет земную связь пациента.",
            "Временная связь с травмой поддерживает психологическое прочтение."
        ],
        "counterevidence": [
            "Астрономические знания Прота и поведение Бесс осложняют такую гипотезу."
        ],
        "unresolved": [
            "Исчезновение Бесс и помехи видеозаписи не объяснены независимо."
        ],
        "final_answer": (
            "Мой вывод: история намеренно не определяет природу Прота однозначно. "
            "Роберт Портер пережил трагедию семьи, поэтому психологическая версия многое объясняет. "
            "Однако необычные астрономические сведения и исчезновение Бесс остаются открытыми "
            "вопросами, а не доказательством внеземного путешествия. "
            "Выбираю неопределённость: ни одно из объяснений не исключает другое полностью."
        )
    }


class ReasonerContract(unittest.TestCase):
    def test_structured_answer_grounded(self):
        result = r.examine(good())
        self.assertEqual(result["research_quality_gate"], "PASS_SOURCE_GROUNDED_SMOKE")
        self.assertEqual(result["source_grounding_hits"], 5)
        self.assertFalse(result["is_independent_generalization_proof"])

    def test_not_faking_superior_model_or_mutation(self):
        self.assertEqual(r.MODEL, "qwen2.5:3b-instruct-q4_K_M")
        self.assertEqual(r.ENDPOINT, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(len(r.SOURCE_SHA256), 64)
        self.assertNotEqual(r.SOURCE_SHA256, "0" * 64)

    def test_weak_prior_repetitious_model_text_would_not_pass(self):
        weak = {
            "hypothesis": "psychological", "confidence": "high",
            "evidence_for": ["Состояние здоровья", "Состояние здоровья"],
            "counterevidence": ["Нет"], "unresolved": ["Нет"],
            "final_answer": "Не знаю."
        }
        with self.assertRaises(ValueError):
            r.examine(weak)

    def test_no_invented_film_hypothesis(self):
        weak = good()
        weak["hypothesis"] = "certain_alien"
        with self.assertRaisesRegex(ValueError, "NO_RECOGNIZED_HYPOTHESIS"):
            r.examine(weak)

    def test_missing_bess_or_porter_is_held_not_passed(self):
        weak = good()
        weak["evidence_for"] = [
            "Загадочная версия восстанавливает необычные события.",
            "Другая версия также имеет основания внутри сюжета."
        ]
        weak["counterevidence"] = ["Дополнительные наблюдения не исключают гипотезу."]
        weak["unresolved"] = ["Финальный эпизод остаётся неясным и сложным."]
        weak["final_answer"] = (
            "Нам неизвестно, какая версия правильна, потому что рассказ сохраняет "
            "неясность и предположения. Это художественный ход, а не доказанный "
            "факт о физике. Требуются более подробные прямые данные из сюжета. "
            "Нельзя утверждать объективно окончательную природу героя."
        )
        result = r.examine(weak)
        self.assertEqual(result["research_quality_gate"], "HOLD_INSUFFICIENT_EVIDENCE_SPECIFICITY")

    def test_projection_respects_source_boundaries(self):
        case = {
            "work": {"original_title": "K-PAX"},
            "abstract": "Художественный текст",
            "ending": {
                "observed": ["Бесс исчезает"],
                "not_shown_or_not_proved": ["Перелёт не зарегистрирован"],
                "core_ambiguity": "Неопределённость"
            },
            "backstory_reconstruction": {"reported_sequence": ["Трагедия Роберта"]},
            "detailed_plot_chronology": [
                {"step": 6, "event": "Знание звёзд"},
                {"step": 19, "event": "Финал"}
            ],
            "competing_interpretations": [
                {"id": "H1", "hypothesis": "Травма", "supporting_clues": ["семья"],
                 "unresolved_observations": ["Бесс"]}
            ],
            "evidence_matrix": [{"observation": "Бесс", "limits": "Недоказано"}]
        }
        projected = json.loads(r.project_evidence(case))
        self.assertEqual(projected["timeline"], [{"step": 6, "event": "Знание звёзд"}])
        self.assertEqual(projected["screen_observations"], ["Бесс исчезает"])
        self.assertNotIn("detailed_plot_chronology", projected)

    def test_verdict_schema_requires_prose_not_array(self):
        self.assertEqual(r.VERDICT_SCHEMA["properties"]["final_answer"]["type"], "string")
        self.assertEqual(set(r.VERDICT_SCHEMA["required"]), set(good().keys()))

    def test_film_false_mediator_cannot_pass(self):
        item = good()
        item["unresolved"] = ["Бесс могла быть посредником между мирами."]
        result = r.examine(item)
        self.assertEqual(result["research_quality_gate"], "HOLD_UNSUPPORTED_SOURCE_CLAIM")

    def test_porter_misattribution_cannot_pass(self):
        item = good()
        item["evidence_for"][0] = "Роберт Портер заявляет, что прибыл с Ка-Пэкс."
        result = r.examine(item)
        self.assertEqual(result["research_quality_gate"], "HOLD_UNSUPPORTED_SOURCE_CLAIM")

    def test_no_remote_host_from_source(self):
        self.assertTrue(r.ENDPOINT.startswith("http://127.0.0.1:"))
        self.assertFalse(hasattr(r, "auto_promote"))
        self.assertFalse(hasattr(r, "dispatch_sentinel"))


if __name__ == "__main__":
    unittest.main()
