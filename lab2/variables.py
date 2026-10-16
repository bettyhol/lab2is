from __future__ import annotations

from models import VariableMetadata


VARIABLES: dict[str, VariableMetadata] = {
    "oxygen_level": VariableMetadata(
        "oxygen_level", "Рівень кисню", (("normal", "Нормальний"), ("low", "Низький")), True
    ),
    "pressure": VariableMetadata(
        "pressure", "Тиск у корпусі", (("stable", "Стабільний"), ("falling", "Падає")), True
    ),
    "hull_sensor": VariableMetadata(
        "hull_sensor", "Стан датчика корпусу", (("intact", "Пошкоджень немає"), ("damaged", "Зафіксовано пошкодження")), True
    ),
    "generator": VariableMetadata(
        "generator", "Генератор", (("operational", "Працює"), ("failed", "Відмова")), True
    ),
    "battery_level": VariableMetadata(
        "battery_level", "Рівень батареї", (("normal", "Нормальний"), ("low", "Низький")), True
    ),
    "communication_module": VariableMetadata(
        "communication_module", "Модуль зв'язку", (("operational", "Працює"), ("failed", "Відмова")), True
    ),
    "antenna": VariableMetadata(
        "antenna", "Антена", (("intact", "Не пошкоджена"), ("damaged", "Пошкоджена")), True
    ),
    "engine_temperature": VariableMetadata(
        "engine_temperature", "Температура двигуна", (("normal", "Нормальна"), ("high", "Висока")), True
    ),
    "cooling_system": VariableMetadata(
        "cooling_system", "Система охолодження", (("operational", "Працює"), ("failed", "Відмова")), True
    ),
    "navigation_system": VariableMetadata(
        "navigation_system", "Навігаційна система", (("operational", "Працює"), ("failed", "Відмова")), True
    ),
    "atmosphere_leak": VariableMetadata(
        "atmosphere_leak", "Витік атмосфери", (("detected", "Виявлено"),), False
    ),
    "power_problem": VariableMetadata(
        "power_problem", "Проблема енергосистеми", (("critical", "Критична"),), False
    ),
    "communication_problem": VariableMetadata(
        "communication_problem", "Проблема зв'язку", (("detected", "Виявлено"),), False
    ),
    "engine_overheating": VariableMetadata(
        "engine_overheating", "Перегрів двигуна", (("critical", "Критичний"),), False
    ),
    "incident": VariableMetadata(
        "incident",
        "Аварійна ситуація",
        (
            ("hull_breach", "Розгерметизація корпусу"),
            ("power_system_failure", "Аварія енергосистеми"),
            ("communication_system_failure", "Несправність системи зв'язку"),
            ("engine_cooling_failure", "Відмова охолодження двигуна"),
        ),
        False,
    ),
    "recommended_action": VariableMetadata(
        "recommended_action",
        "Рекомендована дія",
        (
            ("isolate_damaged_compartment", "Ізолювати пошкоджений відсік"),
            ("emergency_engine_shutdown", "Виконати аварійне вимкнення двигуна"),
        ),
        False,
    ),
}


INPUT_VARIABLES: tuple[str, ...] = tuple(
    name for name, metadata in VARIABLES.items() if metadata.is_input
)
