from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

from models import Fact, ValueSource


class WorkingMemory:
    """Ізольоване сховище фактів одного сеансу експертизи."""

    def __init__(self, variables: Iterable[str]) -> None:
        self._facts = {name: Fact(variable=name) for name in variables}

    def set_fact(self, variable: str, value: str, source: ValueSource) -> bool:
        if variable not in self._facts:
            self._facts[variable] = Fact(variable=variable)
        fact = self._facts[variable]
        if fact.initialized:
            if fact.value != value:
                raise ValueError(
                    f"Суперечливі значення для {variable}: {fact.value!r} і {value!r}"
                )
            return False
        fact.initialized = True
        fact.value = value
        fact.source = source
        return True

    def get_value(self, variable: str) -> Optional[str]:
        fact = self._facts.get(variable)
        return fact.value if fact and fact.initialized else None

    def is_initialized(self, variable: str) -> bool:
        fact = self._facts.get(variable)
        return bool(fact and fact.initialized)

    def get_fact(self, variable: str) -> Fact:
        return self._facts[variable]

    def all_facts(self) -> tuple[Fact, ...]:
        return tuple(self._facts.values())

    def initialized_facts(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self._facts.values() if fact.initialized)
