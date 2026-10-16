from __future__ import annotations

from models import Conclusion, Condition, Rule


def build_knowledge_base() -> tuple[Rule, ...]:
    """Створює ту саму незалежну базу з 10 правил, що й у lab1."""

    return (
        Rule("R1", (Condition("oxygen_level", "low"), Condition("pressure", "falling")), Conclusion("atmosphere_leak", "detected"), "Виявлення витоку атмосфери"),
        Rule("R2", (Condition("atmosphere_leak", "detected"), Condition("hull_sensor", "damaged")), Conclusion("incident", "hull_breach"), "Діагностика розгерметизації корпусу"),
        Rule("R3", (Condition("incident", "hull_breach"),), Conclusion("recommended_action", "isolate_damaged_compartment"), "Ізоляція пошкодженого відсіку"),
        Rule("R4", (Condition("generator", "failed"), Condition("battery_level", "low")), Conclusion("power_problem", "critical"), "Виявлення критичної проблеми живлення"),
        Rule("R5", (Condition("power_problem", "critical"),), Conclusion("incident", "power_system_failure"), "Діагностика аварії енергосистеми"),
        Rule("R6", (Condition("communication_module", "failed"), Condition("antenna", "damaged")), Conclusion("communication_problem", "detected"), "Виявлення проблеми зв'язку"),
        Rule("R7", (Condition("communication_problem", "detected"),), Conclusion("incident", "communication_system_failure"), "Діагностика несправності системи зв'язку"),
        Rule("R8", (Condition("engine_temperature", "high"), Condition("cooling_system", "failed")), Conclusion("engine_overheating", "critical"), "Виявлення критичного перегріву двигуна"),
        Rule("R9", (Condition("engine_overheating", "critical"),), Conclusion("incident", "engine_cooling_failure"), "Діагностика відмови охолодження двигуна"),
        Rule("R10", (Condition("incident", "engine_cooling_failure"),), Conclusion("recommended_action", "emergency_engine_shutdown"), "Аварійне вимкнення двигуна"),
    )


KNOWLEDGE_BASE: tuple[Rule, ...] = build_knowledge_base()
