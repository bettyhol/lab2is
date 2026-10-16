from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ValueSource(Enum):
    """Джерело факту в робочій пам'яті."""

    USER = "USER"
    RULE = "RULE"
    SCENARIO = "SCENARIO"


@dataclass(frozen=True)
class Condition:
    variable: str
    expected_value: str


@dataclass(frozen=True)
class Conclusion:
    variable: str
    value: str


@dataclass(frozen=True)
class Goal:
    """Пара «змінна — очікуване значення», яку потрібно довести."""

    variable: str
    value: str

    def __str__(self) -> str:
        return f"{self.variable} = {self.value}"


@dataclass(frozen=True)
class Rule:
    """Продукційне правило без залежностей від механізму виведення та UI."""

    id: str
    conditions: tuple[Condition, ...]
    conclusion: Conclusion
    description: str


@dataclass
class Fact:
    """Стан однієї змінної в робочій пам'яті."""

    variable: str
    initialized: bool = False
    value: Optional[str] = None
    source: Optional[ValueSource] = None


@dataclass(frozen=True)
class VariableMetadata:
    name: str
    label: str
    values: tuple[tuple[str, str], ...]
    is_input: bool

    @property
    def allowed_values(self) -> tuple[str, ...]:
        return tuple(value for value, _ in self.values)

    def value_label(self, value: str) -> str:
        return dict(self.values).get(value, value)


@dataclass(frozen=True)
class StackEvent:
    """Операція над стеком і його стан одразу після операції."""

    action: str
    goal: Goal
    stack: tuple[Goal, ...]


@dataclass(frozen=True)
class ProtocolEntry:
    """Один крок повного протоколу з condition pointer за потреби."""

    step: int
    event: str
    goal: Goal
    stack: tuple[Goal, ...]
    rule_id: Optional[str] = None
    condition_number: Optional[int] = None
    variable: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    result: Optional[bool] = None
    source: Optional[ValueSource] = None
    message: str = ""


@dataclass(frozen=True)
class ChainEntry:
    """Динамічний елемент логічного ланцюга: факт або правило."""

    kind: str
    variable: Optional[str] = None
    value: Optional[str] = None
    source: Optional[ValueSource] = None
    rule: Optional[Rule] = None
