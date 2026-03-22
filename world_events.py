# world_events.py
# Интерпретация метрик обучения в игровые события

from typing import Dict, Any, Tuple, List

CONFIG = {
    'lethal_damage': 40,
    'damage_per_loss_increase': 5,
    'exp_per_loss_decrease': 10,
    'base_damage': 5
}


def interpret_metrics(metrics: Dict[str, Any], janus_state: Any) -> Tuple[str, List[str], str]:
    """
    Обновляет состояние RPG на основе метрик обучения.
    Возвращает кортеж (event_type, combat_log, description).
    """
    if not metrics:
        return "neutral", [], ""

    loss = metrics.get("loss")
    prev_loss = metrics.get("prev_loss")
    lethal = metrics.get("lethal", False)

    combat_log = []

    if lethal:
        janus_state.health -= CONFIG['lethal_damage']
        if janus_state.health < 0:
            janus_state.health = 0
        combat_log.append(f"💀 ВЗРЫВ ГРАДИЕНТОВ! Янус теряет {CONFIG['lethal_damage']} HP.")
        return "lethal", combat_log, "Катастрофический взрыв градиентов"

    if loss is None:
        return "neutral", combat_log, ""

    # Проверка на NaN
    if loss != loss:  # NaN
        janus_state.health -= CONFIG['lethal_damage']
        combat_log.append(f"💀 NaN loss! Янус теряет {CONFIG['lethal_damage']} HP.")
        return "lethal", combat_log, "Потеря градиентов"

    if prev_loss is not None:
        if loss < prev_loss:
            dmg = (prev_loss - loss) * 10
            xp_gain = int(dmg)
            janus_state.exp += xp_gain
            combat_log.append(f"⚔️ Янус атакует Хаос! Loss {prev_loss:.4f} → {loss:.4f}")
            combat_log.append(f"✨ Получено {xp_gain} XP")
            return "victory", combat_log, "Успешная атака"
        else:
            damage = CONFIG['base_damage'] + int((loss - prev_loss) * 5)
            janus_state.health -= damage
            combat_log.append(f"💥 Янус получает урон! Loss {prev_loss:.4f} → {loss:.4f}")
            combat_log.append(f"❤️ Потеряно {damage} HP")
            return "damage", combat_log, "Контратака хаоса"

    return "neutral", combat_log, ""