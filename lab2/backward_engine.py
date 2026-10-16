from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Optional

from models import (
    ChainEntry,
    Goal,
    ProtocolEntry,
    Rule,
    StackEvent,
    ValueSource,
    VariableMetadata,
)
from working_memory import WorkingMemory


FactProvider = Callable[[str], Optional[str]]


class InferenceStack:
    """Явний LIFO-стек цілей логічного виведення."""

    def __init__(self) -> None:
        self._items: list[Goal] = []
        self._history: list[StackEvent] = []

    def push(self, goal: Goal) -> None:
        self._items.append(goal)
        self._history.append(StackEvent("PUSH", goal, self.snapshot()))

    def pop(self) -> Goal:
        if self.is_empty():
            raise IndexError("Спроба видалити елемент із порожнього стеку")
        goal = self._items.pop()
        self._history.append(StackEvent("POP", goal, self.snapshot()))
        return goal

    def peek(self) -> Goal:
        if self.is_empty():
            raise IndexError("Порожній стек не має вершини")
        return self._items[-1]

    def is_empty(self) -> bool:
        return not self._items

    def snapshot(self) -> tuple[Goal, ...]:
        return tuple(self._items)

    @property
    def history(self) -> tuple[StackEvent, ...]:
        return tuple(self._history)


@dataclass(frozen=True)
class InferenceResult:
    """Повний результат одного незалежного запуску backward chaining."""

    goal: Goal
    proved: bool
    working_memory: WorkingMemory
    fired_rules: tuple[Rule, ...]
    protocol: tuple[ProtocolEntry, ...]
    stack_history: tuple[StackEvent, ...]
    asked_variables: tuple[str, ...]
    chain_entries: tuple[ChainEntry, ...]

    @property
    def logical_chain(self) -> tuple[Rule, ...]:
        return tuple(
            entry.rule
            for entry in self.chain_entries
            if entry.kind == "RULE" and entry.rule is not None
        )

    @property
    def fired_rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.fired_rules)


class BackwardInferenceEngine:
    """Goal-driven механізм зворотного логічного виведення."""

    def __init__(
        self,
        rules: Sequence[Rule],
        variables: Mapping[str, VariableMetadata],
    ) -> None:
        self.rules = tuple(rules)
        self.variables = dict(variables)
        self.rules_by_conclusion = self._build_rule_index()
        self.conclusion_variables = self._ordered_conclusion_variables()
        self.condition_variables = self._ordered_condition_variables()
        self._conclusion_variable_set = set(self.conclusion_variables)
        self._validate_knowledge_base()

    def _build_rule_index(self) -> dict[tuple[str, str], tuple[Rule, ...]]:
        index: defaultdict[tuple[str, str], list[Rule]] = defaultdict(list)
        for rule in self.rules:
            key = (rule.conclusion.variable, rule.conclusion.value)
            index[key].append(rule)
        return {key: tuple(rules) for key, rules in index.items()}

    def _ordered_conclusion_variables(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(rule.conclusion.variable for rule in self.rules))

    def _ordered_condition_variables(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                condition.variable
                for rule in self.rules
                for condition in rule.conditions
            )
        )

    def _validate_knowledge_base(self) -> None:
        rule_ids: set[str] = set()
        for rule in self.rules:
            if rule.id in rule_ids:
                raise ValueError(f"Повторний ID правила: {rule.id}")
            rule_ids.add(rule.id)
            if not rule.conditions:
                raise ValueError(f"Правило {rule.id} не має умов")
            for condition in rule.conditions:
                self._validate_value(condition.variable, condition.expected_value)
            self._validate_value(rule.conclusion.variable, rule.conclusion.value)

    def _validate_value(self, variable: str, value: str) -> None:
        metadata = self.variables.get(variable)
        if metadata is None:
            raise ValueError(f"Невідома змінна: {variable}")
        if value not in metadata.allowed_values:
            raise ValueError(f"Недопустиме значення {value!r} для {variable}")

    def infer(
        self,
        goal: Goal,
        fact_provider: Optional[FactProvider] = None,
        *,
        initial_facts: Optional[Mapping[str, str]] = None,
        initial_source: ValueSource = ValueSource.SCENARIO,
    ) -> InferenceResult:
        """Доводить лише задану ціль, створюючи чистий стан для запуску."""

        self._validate_value(goal.variable, goal.value)
        memory = WorkingMemory(self.variables)
        stack = InferenceStack()
        protocol: list[ProtocolEntry] = []
        fired_rules: list[Rule] = []
        fired_ids: set[str] = set()
        asked_variables: list[str] = []
        requested: set[str] = set()
        currently_proving: set[Goal] = set()
        chain_entries: list[ChainEntry] = []
        step = 0

        def trace(
            event: str,
            current_goal: Goal,
            *,
            rule_id: Optional[str] = None,
            condition_number: Optional[int] = None,
            variable: Optional[str] = None,
            expected_value: Optional[str] = None,
            actual_value: Optional[str] = None,
            result: Optional[bool] = None,
            source: Optional[ValueSource] = None,
            message: str = "",
        ) -> None:
            nonlocal step
            step += 1
            protocol.append(
                ProtocolEntry(
                    step=step,
                    event=event,
                    goal=current_goal,
                    stack=stack.snapshot(),
                    rule_id=rule_id,
                    condition_number=condition_number,
                    variable=variable,
                    expected_value=expected_value,
                    actual_value=actual_value,
                    result=result,
                    source=source,
                    message=message,
                )
            )

        def push(current_goal: Goal) -> None:
            stack.push(current_goal)
            trace("PUSH", current_goal, message="Ціль додано на вершину стеку")

        def pop(current_goal: Goal) -> None:
            if stack.peek() != current_goal:
                raise RuntimeError("Порушено LIFO-порядок стеку логічного виведення")
            stack.pop()
            trace("POP", current_goal, message="Ціль знято з вершини стеку")

        for variable, value in (initial_facts or {}).items():
            self._validate_value(variable, value)
            memory.set_fact(variable, value, initial_source)

        def prove(current_goal: Goal, proof_entries: list[ChainEntry]) -> bool:
            if memory.is_initialized(current_goal.variable):
                actual = memory.get_value(current_goal.variable)
                result = actual == current_goal.value
                source = memory.get_fact(current_goal.variable).source
                trace(
                    "KNOWN_FACT",
                    current_goal,
                    variable=current_goal.variable,
                    expected_value=current_goal.value,
                    actual_value=actual,
                    result=result,
                    source=source,
                    message="Перевірено факт із робочої пам'яті",
                )
                if result:
                    proof_entries.append(
                        ChainEntry(
                            "FACT",
                            current_goal.variable,
                            current_goal.value,
                            source,
                        )
                    )
                pop(current_goal)
                return result

            if current_goal in currently_proving:
                trace(
                    "CYCLE",
                    current_goal,
                    result=False,
                    message="Виявлено циклічну залежність у поточному шляху",
                )
                pop(current_goal)
                return False

            currently_proving.add(current_goal)
            try:
                candidate_rules = self.rules_by_conclusion.get(
                    (current_goal.variable, current_goal.value), ()
                )

                if not candidate_rules:
                    if current_goal.variable in self._conclusion_variable_set:
                        trace(
                            "NO_RULE",
                            current_goal,
                            result=False,
                            message="Для цього значення вивідної змінної немає правила",
                        )
                        return False

                    if current_goal.variable not in requested:
                        requested.add(current_goal.variable)
                        asked_variables.append(current_goal.variable)
                        trace(
                            "ASK",
                            current_goal,
                            variable=current_goal.variable,
                            expected_value=current_goal.value,
                            message="Запит базового факту через FactProvider",
                        )
                        supplied = (
                            fact_provider(current_goal.variable)
                            if fact_provider is not None
                            else None
                        )
                        if supplied is not None:
                            self._validate_value(current_goal.variable, supplied)
                            memory.set_fact(
                                current_goal.variable, supplied, ValueSource.USER
                            )

                    actual = memory.get_value(current_goal.variable)
                    result = actual == current_goal.value
                    source = (
                        memory.get_fact(current_goal.variable).source
                        if memory.is_initialized(current_goal.variable)
                        else None
                    )
                    trace(
                        "BASE_FACT",
                        current_goal,
                        variable=current_goal.variable,
                        expected_value=current_goal.value,
                        actual_value=actual,
                        result=result,
                        source=source,
                        message="Перевірено значення базового факту",
                    )
                    if result:
                        proof_entries.append(
                            ChainEntry(
                                "FACT",
                                current_goal.variable,
                                current_goal.value,
                                source,
                            )
                        )
                    return result

                for rule in candidate_rules:
                    branch_entries: list[ChainEntry] = []
                    trace(
                        "RULE_SELECTED",
                        current_goal,
                        rule_id=rule.id,
                        message=f"Перевірка правила: {rule.description}",
                    )
                    rule_succeeded = True

                    for number, condition in enumerate(rule.conditions, start=1):
                        condition_goal = Goal(
                            condition.variable, condition.expected_value
                        )
                        condition_entries: list[ChainEntry] = []
                        if memory.is_initialized(condition.variable):
                            actual = memory.get_value(condition.variable)
                            condition_result = actual == condition.expected_value
                            if condition_result:
                                condition_entries.append(
                                    ChainEntry(
                                        "FACT",
                                        condition.variable,
                                        condition.expected_value,
                                        memory.get_fact(condition.variable).source,
                                    )
                                )
                        elif condition.variable in self._conclusion_variable_set:
                            push(condition_goal)
                            condition_result = prove(
                                condition_goal, condition_entries
                            )
                            actual = memory.get_value(condition.variable)
                        else:
                            # Базові умови не є змінними логічного висновку,
                            # тому до inference stack не додаються.
                            if condition.variable not in requested:
                                requested.add(condition.variable)
                                asked_variables.append(condition.variable)
                                trace(
                                    "ASK",
                                    current_goal,
                                    rule_id=rule.id,
                                    condition_number=number,
                                    variable=condition.variable,
                                    expected_value=condition.expected_value,
                                    message="Запит базового факту через FactProvider",
                                )
                                supplied = (
                                    fact_provider(condition.variable)
                                    if fact_provider is not None
                                    else None
                                )
                                if supplied is not None:
                                    self._validate_value(condition.variable, supplied)
                                    memory.set_fact(
                                        condition.variable,
                                        supplied,
                                        ValueSource.USER,
                                    )
                            actual = memory.get_value(condition.variable)
                            condition_result = actual == condition.expected_value
                            if condition_result:
                                condition_entries.append(
                                    ChainEntry(
                                        "FACT",
                                        condition.variable,
                                        condition.expected_value,
                                        memory.get_fact(condition.variable).source,
                                    )
                                )

                        source = (
                            memory.get_fact(condition.variable).source
                            if memory.is_initialized(condition.variable)
                            else None
                        )
                        trace(
                            "CONDITION",
                            current_goal,
                            rule_id=rule.id,
                            condition_number=number,
                            variable=condition.variable,
                            expected_value=condition.expected_value,
                            actual_value=actual,
                            result=condition_result,
                            source=source,
                            message="Condition Pointer: перевірено умову правила",
                        )

                        if not condition_result:
                            rule_succeeded = False
                            break
                        branch_entries.extend(condition_entries)

                    if not rule_succeeded:
                        trace(
                            "RULE_REJECTED",
                            current_goal,
                            rule_id=rule.id,
                            result=False,
                            message="Хоча б одна умова правила хибна",
                        )
                        continue

                    try:
                        memory.set_fact(
                            rule.conclusion.variable,
                            rule.conclusion.value,
                            ValueSource.RULE,
                        )
                    except ValueError as error:
                        trace(
                            "RULE_REJECTED",
                            current_goal,
                            rule_id=rule.id,
                            result=False,
                            message=str(error),
                        )
                        continue

                    if rule.id not in fired_ids:
                        fired_ids.add(rule.id)
                        fired_rules.append(rule)
                    branch_entries.append(ChainEntry("RULE", rule=rule))
                    proof_entries.extend(branch_entries)
                    trace(
                        "RULE_FIRED",
                        current_goal,
                        rule_id=rule.id,
                        variable=rule.conclusion.variable,
                        actual_value=rule.conclusion.value,
                        result=True,
                        source=ValueSource.RULE,
                        message="Усі умови істинні; висновок додано в пам'ять",
                    )
                    return True

                return False
            finally:
                currently_proving.remove(current_goal)
                pop(current_goal)

        push(goal)
        proved = prove(goal, chain_entries)

        return InferenceResult(
            goal=goal,
            proved=proved,
            working_memory=memory,
            fired_rules=tuple(fired_rules),
            protocol=tuple(protocol),
            stack_history=stack.history,
            asked_variables=tuple(asked_variables),
            chain_entries=tuple(chain_entries),
        )
