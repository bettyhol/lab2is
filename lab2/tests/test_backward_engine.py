from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from backward_engine import BackwardInferenceEngine
from knowledge_base import KNOWLEDGE_BASE
from models import Conclusion, Condition, Goal, Rule, ValueSource, VariableMetadata
from variables import VARIABLES
from ui import ConsoleUI


class FakeFactProvider:
    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def __call__(self, variable: str) -> str | None:
        self.calls.append(variable)
        return self.answers.get(variable)


class BackwardInferenceEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = BackwardInferenceEngine(KNOWLEDGE_BASE, VARIABLES)

    def infer(self, variable: str, value: str, answers: dict[str, str]):
        provider = FakeFactProvider(answers)
        result = self.engine.infer(Goal(variable, value), provider)
        return result, provider

    def test_01_proves_isolation_action(self) -> None:
        result, _ = self.infer(
            "recommended_action",
            "isolate_damaged_compartment",
            {"oxygen_level": "low", "pressure": "falling", "hull_sensor": "damaged"},
        )

        self.assertTrue(result.proved)
        self.assertEqual(("R1", "R2", "R3"), result.fired_rule_ids)

    def test_02_hull_breach_is_not_proved_for_normal_oxygen(self) -> None:
        result, provider = self.infer(
            "incident", "hull_breach", {"oxygen_level": "normal"}
        )

        self.assertFalse(result.proved)
        self.assertEqual(("oxygen_level",), result.asked_variables)
        self.assertEqual(["oxygen_level"], provider.calls)

    def test_03_only_goal_relevant_base_facts_are_requested(self) -> None:
        result, _ = self.infer(
            "incident",
            "hull_breach",
            {"oxygen_level": "low", "pressure": "falling", "hull_sensor": "damaged"},
        )

        unrelated = {
            "generator", "battery_level", "communication_module", "antenna",
            "engine_temperature", "cooling_system",
        }
        self.assertTrue(result.proved)
        self.assertTrue(unrelated.isdisjoint(result.asked_variables))
        self.assertEqual(
            ("oxygen_level", "pressure", "hull_sensor"), result.asked_variables
        )

    def test_04_derived_variable_is_not_requested(self) -> None:
        result, provider = self.infer(
            "atmosphere_leak",
            "detected",
            {"oxygen_level": "low", "pressure": "falling"},
        )

        self.assertTrue(result.proved)
        self.assertNotIn("atmosphere_leak", provider.calls)
        self.assertEqual(("R1",), result.fired_rule_ids)

    def test_05_working_memory_contains_derived_facts(self) -> None:
        result, _ = self.infer(
            "incident",
            "hull_breach",
            {"oxygen_level": "low", "pressure": "falling", "hull_sensor": "damaged"},
        )

        self.assertEqual("detected", result.working_memory.get_value("atmosphere_leak"))
        self.assertEqual("hull_breach", result.working_memory.get_value("incident"))
        self.assertEqual(
            ValueSource.RULE,
            result.working_memory.get_fact("atmosphere_leak").source,
        )

    def test_06_stack_history_demonstrates_lifo(self) -> None:
        result, _ = self.infer(
            "recommended_action",
            "isolate_damaged_compartment",
            {"oxygen_level": "low", "pressure": "falling", "hull_sensor": "damaged"},
        )

        pushes = [event.goal.variable for event in result.stack_history if event.action == "PUSH"]
        pops = [event.goal.variable for event in result.stack_history if event.action == "POP"]
        self.assertEqual(
            ["recommended_action", "incident", "atmosphere_leak"], pushes
        )
        self.assertEqual(list(reversed(pushes)), pops)
        self.assertEqual((), result.stack_history[-1].stack)

    def test_07_logical_chain_has_rule_firing_order(self) -> None:
        result, _ = self.infer(
            "recommended_action",
            "isolate_damaged_compartment",
            {"oxygen_level": "low", "pressure": "falling", "hull_sensor": "damaged"},
        )

        self.assertEqual(["R1", "R2", "R3"], [rule.id for rule in result.logical_chain])

    def test_08_proves_engine_cooling_failure(self) -> None:
        result, _ = self.infer(
            "incident",
            "engine_cooling_failure",
            {"engine_temperature": "high", "cooling_system": "failed"},
        )

        self.assertTrue(result.proved)
        self.assertEqual(("R8", "R9"), result.fired_rule_ids)

    def test_09_proves_emergency_engine_shutdown(self) -> None:
        result, _ = self.infer(
            "recommended_action",
            "emergency_engine_shutdown",
            {"engine_temperature": "high", "cooling_system": "failed"},
        )

        self.assertTrue(result.proved)
        self.assertEqual(("R8", "R9", "R10"), result.fired_rule_ids)

    def test_10_failed_rule_does_not_create_conclusion(self) -> None:
        result, _ = self.infer(
            "incident", "hull_breach", {"oxygen_level": "normal"}
        )

        self.assertIsNone(result.working_memory.get_value("atmosphere_leak"))
        self.assertIsNone(result.working_memory.get_value("incident"))
        self.assertNotIn("R1", result.fired_rule_ids)
        self.assertNotIn("R2", result.fired_rule_ids)

    def test_11_repeated_run_gets_fresh_working_memory(self) -> None:
        first, _ = self.infer(
            "incident",
            "hull_breach",
            {"oxygen_level": "low", "pressure": "falling", "hull_sensor": "damaged"},
        )
        second, _ = self.infer(
            "incident",
            "power_system_failure",
            {"generator": "failed", "battery_level": "low"},
        )

        self.assertIsNot(first.working_memory, second.working_memory)
        self.assertIsNone(second.working_memory.get_value("oxygen_level"))
        self.assertIsNone(second.working_memory.get_value("atmosphere_leak"))
        self.assertEqual(("R4", "R5"), second.fired_rule_ids)

    def test_12_cycle_protection_terminates(self) -> None:
        rules = (
            Rule("C1", (Condition("A", "yes"),), Conclusion("B", "yes"), "A -> B"),
            Rule("C2", (Condition("B", "yes"),), Conclusion("A", "yes"), "B -> A"),
        )
        metadata = {
            name: VariableMetadata(name, name, (("yes", "Так"),), False)
            for name in ("A", "B")
        }
        engine = BackwardInferenceEngine(rules, metadata)

        with patch("builtins.input", side_effect=AssertionError("input() викликано")):
            result = engine.infer(Goal("A", "yes"), lambda _variable: None)

        self.assertFalse(result.proved)
        self.assertTrue(any(entry.event == "CYCLE" for entry in result.protocol))
        self.assertEqual((), result.stack_history[-1].stack)

    def test_exact_conclusion_index_and_lists_are_built_automatically(self) -> None:
        self.assertEqual(("R2",), tuple(rule.id for rule in self.engine.rules_by_conclusion[("incident", "hull_breach")]))
        self.assertIn("incident", self.engine.conclusion_variables)
        self.assertIn("oxygen_level", self.engine.condition_variables)
        self.assertEqual(10, len(self.engine.rules))

    def test_engine_never_calls_console_input(self) -> None:
        with patch("builtins.input", side_effect=AssertionError("input() викликано")):
            result = self.engine.infer(
                Goal("incident", "power_system_failure"),
                {"generator": "failed", "battery_level": "low"}.get,
            )

        self.assertTrue(result.proved)

    def test_initial_facts_are_supported_without_fact_provider(self) -> None:
        result = self.engine.infer(
            Goal("incident", "communication_system_failure"),
            initial_facts={"communication_module": "failed", "antenna": "damaged"},
        )

        self.assertTrue(result.proved)
        self.assertEqual((), result.asked_variables)
        self.assertEqual(("R6", "R7"), result.fired_rule_ids)

    def test_multiple_rules_for_same_conclusion_try_alternative_paths(self) -> None:
        rules = (
            Rule("A1", (Condition("sensor_x", "yes"),), Conclusion("alarm", "on"), "Шлях X"),
            Rule("A2", (Condition("sensor_y", "yes"),), Conclusion("alarm", "on"), "Шлях Y"),
        )
        metadata = {
            "sensor_x": VariableMetadata("sensor_x", "X", (("yes", "Так"), ("no", "Ні")), True),
            "sensor_y": VariableMetadata("sensor_y", "Y", (("yes", "Так"), ("no", "Ні")), True),
            "alarm": VariableMetadata("alarm", "Тривога", (("on", "Увімкнено"),), False),
        }
        engine = BackwardInferenceEngine(rules, metadata)
        provider = FakeFactProvider({"sensor_x": "no", "sensor_y": "yes"})

        result = engine.infer(Goal("alarm", "on"), provider)

        self.assertTrue(result.proved)
        self.assertEqual(("A2",), result.fired_rule_ids)
        self.assertEqual(["sensor_x", "sensor_y"], provider.calls)
        self.assertTrue(
            any(
                entry.event == "RULE_REJECTED" and entry.rule_id == "A1"
                for entry in result.protocol
            )
        )

    def test_missing_fact_provider_answer_fails_cleanly(self) -> None:
        result = self.engine.infer(
            Goal("incident", "hull_breach"), lambda _variable: None
        )

        self.assertFalse(result.proved)
        self.assertEqual(("oxygen_level",), result.asked_variables)
        self.assertEqual((), result.stack_history[-1].stack)
        self.assertEqual((), result.chain_entries)

    def test_base_goal_without_producing_rule_uses_provider(self) -> None:
        result = self.engine.infer(
            Goal("navigation_system", "operational"),
            {"navigation_system": "operational"}.get,
        )

        self.assertTrue(result.proved)
        self.assertEqual(("navigation_system",), result.asked_variables)
        self.assertEqual("operational", result.working_memory.get_value("navigation_system"))

    def test_unknown_goal_is_rejected_predictably(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.infer(Goal("unsupported", "value"), lambda _variable: None)

    def test_negative_proof_does_not_create_opposite_fact(self) -> None:
        result = self.engine.infer(
            Goal("incident", "hull_breach"),
            {"oxygen_level": "normal"}.get,
        )

        self.assertFalse(result.proved)
        incident = result.working_memory.get_fact("incident")
        self.assertFalse(incident.initialized)
        self.assertIsNone(incident.value)

    def test_nested_failed_proof_completely_cleans_stack(self) -> None:
        answers = {"oxygen_level": "low"}
        result = self.engine.infer(
            Goal("recommended_action", "isolate_damaged_compartment"),
            answers.get,
        )

        self.assertFalse(result.proved)
        self.assertEqual((), result.stack_history[-1].stack)
        self.assertEqual((), result.chain_entries)

    def test_rejected_alternative_is_excluded_from_final_proof(self) -> None:
        engine, provider = self._alternative_engine()

        result = engine.infer(Goal("alarm", "on"), provider)
        facts = [
            (entry.variable, entry.value)
            for entry in result.chain_entries
            if entry.kind == "FACT"
        ]

        self.assertTrue(result.proved)
        self.assertEqual([("sensor_y", "yes")], facts)
        self.assertEqual(["A2"], [
            entry.rule.id
            for entry in result.chain_entries
            if entry.kind == "RULE" and entry.rule is not None
        ])
        self.assertEqual(["A2"], [rule.id for rule in result.logical_chain])

    def test_rejected_alternative_remains_in_protocol(self) -> None:
        engine, provider = self._alternative_engine()

        result = engine.infer(Goal("alarm", "on"), provider)

        self.assertTrue(any(
            entry.event == "CONDITION"
            and entry.rule_id == "A1"
            and entry.actual_value == "no"
            for entry in result.protocol
        ))
        self.assertTrue(any(
            entry.event == "RULE_REJECTED" and entry.rule_id == "A1"
            for entry in result.protocol
        ))

    def test_console_unknown_answer_returns_none_without_crash(self) -> None:
        output = StringIO()
        with patch("builtins.input", return_value="0"), redirect_stdout(output):
            answer = ConsoleUI(self.engine)._console_fact_provider("oxygen_level")

        self.assertIsNone(answer)
        self.assertIn("UNKNOWN", output.getvalue())

    @staticmethod
    def _alternative_engine() -> tuple[BackwardInferenceEngine, FakeFactProvider]:
        rules = (
            Rule("A1", (Condition("sensor_x", "yes"),), Conclusion("alarm", "on"), "Шлях X"),
            Rule("A2", (Condition("sensor_y", "yes"),), Conclusion("alarm", "on"), "Шлях Y"),
        )
        metadata = {
            "sensor_x": VariableMetadata("sensor_x", "X", (("yes", "Так"), ("no", "Ні")), True),
            "sensor_y": VariableMetadata("sensor_y", "Y", (("yes", "Так"), ("no", "Ні")), True),
            "alarm": VariableMetadata("alarm", "Тривога", (("on", "Увімкнено"),), False),
        }
        return BackwardInferenceEngine(rules, metadata), FakeFactProvider(
            {"sensor_x": "no", "sensor_y": "yes"}
        )


if __name__ == "__main__":
    unittest.main()
