from __future__ import annotations

from backward_engine import BackwardInferenceEngine, InferenceResult
from goals import GOAL_OPTIONS
from models import Goal, ProtocolEntry, Rule
from variables import VARIABLES


LINE = "=" * 62


class ConsoleUI:
    """Україномовний CLI; увесь console input ізольований від рушія."""

    def __init__(self, engine: BackwardInferenceEngine) -> None:
        self.engine = engine

    def run(self) -> None:
        self._show_header()
        while True:
            goal = self._choose_goal()
            if goal is None:
                self._goodbye()
                return

            print(f"\nTARGET:\n{goal}")
            print("\n[INFERENCE] Пошук правил і необхідних базових фактів...")
            result = self.engine.infer(goal, self._console_fact_provider)
            self._show_inference_summary(result)
            self._show_result(result)

            if not self._result_menu(result):
                self._goodbye()
                return
            self._show_header()

    def _show_header(self) -> None:
        print(f"\n{LINE}")
        print("       SPACECRAFT EMERGENCY EXPERT SYSTEM")
        print(LINE)
        print("Expert system ........ ONLINE")
        print(f"Knowledge base ....... {len(self.engine.rules)} rules")
        print("Inference mode ....... BACKWARD CHAINING")
        print("Data structure ....... LIFO STACK")

    def _choose_goal(self) -> Goal | None:
        print("\nОберіть гіпотезу для перевірки:\n")
        for number, option in enumerate(GOAL_OPTIONS, start=1):
            print(f"{number}. {option.label}")
        print("0. Вихід")
        choice = self._read_choice(0, len(GOAL_OPTIONS))
        return None if choice == 0 else GOAL_OPTIONS[choice - 1].goal

    @staticmethod
    def _read_choice(minimum: int, maximum: int) -> int:
        while True:
            raw = input("\nВаш вибір: ").strip()
            try:
                choice = int(raw)
            except ValueError:
                print("Введіть номер пункту меню.")
                continue
            if minimum <= choice <= maximum:
                return choice
            print(f"Оберіть число від {minimum} до {maximum}.")

    def _console_fact_provider(self, variable: str) -> str | None:
        metadata = VARIABLES[variable]
        print(f"\n[BASE FACT] {metadata.label}")
        for number, (_, label) in enumerate(metadata.values, start=1):
            print(f"{number}. {label}")
        print("0. Невідомо")
        choice = self._read_choice(0, len(metadata.values))
        if choice == 0:
            print(f"[USER] {variable} = UNKNOWN")
            return None
        value = metadata.values[choice - 1][0]
        print(f"[USER] {variable} = {value}")
        return value

    @staticmethod
    def _show_inference_summary(result: InferenceResult) -> None:
        for entry in result.protocol:
            if entry.event == "RULE_FIRED":
                print(f"[RULE FIRED] {entry.rule_id} -> {entry.variable} = {entry.actual_value}")
            elif entry.event == "RULE_REJECTED":
                print(f"[RULE REJECTED] {entry.rule_id}")
            elif entry.event == "CYCLE":
                print(f"[CYCLE] {entry.goal}")

    @staticmethod
    def _show_result(result: InferenceResult) -> None:
        print(f"\n{LINE}")
        print("РЕЗУЛЬТАТ ЕКСПЕРТИЗИ")
        print(LINE)
        print(f"\nЦіль:\n{result.goal}")
        print(f"\nСтатус:\n{'ДОВЕДЕНО' if result.proved else 'НЕ ДОВЕДЕНО'}")
        chain = " -> ".join(result.fired_rule_ids)
        print(f"\nСпрацювали правила:\n{chain or 'Жодне'}")
        print(
            f"\nОтримано фактів:\n"
            f"{len(result.working_memory.initialized_facts())}"
        )
        print(LINE)

    def _result_menu(self, result: InferenceResult) -> bool:
        while True:
            print("\n1. Показати логічний ланцюг")
            print("2. Показати робочу пам'ять")
            print("3. Показати стек / історію стеку")
            print("4. Показати повний протокол")
            print("5. Нова експертиза")
            print("0. Вихід")
            choice = self._read_choice(0, 5)
            if choice == 1:
                self._show_logical_chain(result)
            elif choice == 2:
                self._show_working_memory(result)
            elif choice == 3:
                self._show_stack_history(result)
            elif choice == 4:
                self._show_protocol(result)
            elif choice == 5:
                return True
            else:
                return False

    @staticmethod
    def _show_logical_chain(result: InferenceResult) -> None:
        print(f"\n{LINE}\nЛОГІЧНИЙ ЛАНЦЮГ\n{LINE}")
        print(f"\nЦіль:\n{result.goal}\n\nДоведення:")
        if not result.chain_entries:
            print("Ланцюг порожній.")
        for number, entry in enumerate(result.chain_entries, start=1):
            if entry.kind == "FACT":
                source = entry.source.value if entry.source else "—"
                print(f"\n{number}. {entry.variable} = {entry.value}\n   [{source}]")
            elif entry.rule is not None:
                print(f"\n{number}. {rule_to_text(entry.rule)}")
        print(f"\nВИСНОВОК:\n{result.goal}\n")
        print("ДОВЕДЕНО." if result.proved else "НЕ ДОВЕДЕНО.")
        print(LINE)

    @staticmethod
    def _show_working_memory(result: InferenceResult) -> None:
        print(f"\n{LINE}\nРОБОЧА ПАМ'ЯТЬ\n{LINE}")
        print(f"{'Змінна':<27} {'Initialized':<12} {'Значення':<31} Джерело")
        for fact in result.working_memory.all_facts():
            value = fact.value if fact.initialized else "—"
            source = fact.source.value if fact.source else "—"
            print(
                f"{fact.variable:<27} {str(fact.initialized):<12} "
                f"{value:<31} {source}"
            )

    @staticmethod
    def _show_stack_history(result: InferenceResult) -> None:
        print(f"\n{LINE}\nІСТОРІЯ LIFO-СТЕКУ\n{LINE}")
        for event in result.stack_history:
            state = " -> ".join(
                f"{goal.variable}={goal.value}" for goal in event.stack
            )
            print(f"\n[{event.action}] {event.goal}")
            print(f"STACK: {state or '[порожній]'}")

    @staticmethod
    def _show_protocol(result: InferenceResult) -> None:
        print(f"\n{LINE}\nПОВНИЙ ПРОТОКОЛ\n{LINE}")
        for entry in result.protocol:
            print(format_protocol_entry(entry))

    @staticmethod
    def _goodbye() -> None:
        print("\nБортову експертну систему завершено.")


def rule_to_text(rule: Rule) -> str:
    conditions = " AND ".join(
        f"{condition.variable} = {condition.expected_value}"
        for condition in rule.conditions
    )
    conclusion = rule.conclusion
    return f"{rule.id}: {conditions} -> {conclusion.variable} = {conclusion.value}"


def format_protocol_entry(entry: ProtocolEntry) -> str:
    stack = " -> ".join(f"{goal.variable}={goal.value}" for goal in entry.stack)
    parts = [f"#{entry.step:02d} [{entry.event}]", f"goal: {entry.goal}"]
    if entry.rule_id:
        parts.append(f"rule: {entry.rule_id}")
    if entry.condition_number is not None:
        parts.append(f"condition: {entry.condition_number}")
    if entry.variable:
        comparison = entry.variable
        if entry.expected_value is not None:
            comparison += f" expected={entry.expected_value}"
        if entry.actual_value is not None:
            comparison += f" actual={entry.actual_value}"
        parts.append(comparison)
    if entry.result is not None:
        parts.append("result: TRUE" if entry.result else "result: FALSE")
    if entry.source:
        parts.append(f"source: {entry.source.value}")
    parts.append(f"stack: {stack or '[порожній]'}")
    if entry.message:
        parts.append(entry.message)
    return " | ".join(parts)
