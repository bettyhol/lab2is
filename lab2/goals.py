from __future__ import annotations

from dataclasses import dataclass

from models import Goal


@dataclass(frozen=True)
class GoalOption:
    label: str
    goal: Goal


GOAL_OPTIONS: tuple[GoalOption, ...] = (
    GoalOption("Пробоїна корпусу", Goal("incident", "hull_breach")),
    GoalOption("Відмова енергосистеми", Goal("incident", "power_system_failure")),
    GoalOption("Несправність системи зв'язку", Goal("incident", "communication_system_failure")),
    GoalOption("Відмова охолодження двигуна", Goal("incident", "engine_cooling_failure")),
    GoalOption("Ізолювати пошкоджений відсік", Goal("recommended_action", "isolate_damaged_compartment")),
    GoalOption("Аварійно вимкнути двигун", Goal("recommended_action", "emergency_engine_shutdown")),
)
