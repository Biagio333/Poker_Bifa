import json
import re
import subprocess


DEFAULT_OLLAMA_MODEL = "hf.co/mradermacher/poker-reasoning-14b-GGUF:Q3_K_S"


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_ollama_prompt(table, hero_equity=None, hero_position=None, big_blind=None):
    hero = table.get_player(table.hero_seat)

    players_summary = []
    for player in table.players:
        players_summary.append({
            "seat": player.seat,
            "stack": player.stack,
            "type": player.player_type,
        })

    players_in_hand = sum(1 for player in table.players if player.in_hand)
    if players_in_hand <= 0:
        players_in_hand = None

    state = {
        "street": table.street,
        "pot": table.pot,
        "hero_cards": table.hero_cards,
        "hero_position": hero_position,
        "hero_stack": hero.stack,
        "hero_bet": hero.current_bet,
        "big_blind": big_blind,
        "players_in_hand": players_in_hand,
        "players": players_summary,
        "available_actions": [action.get("label", "") for action in table.available_actions],
    }

    if table.board_cards:
        state["board_cards"] = table.board_cards
    if hero_equity is not None:
        state["hero_equity"] = _safe_float(hero_equity)

    return (
        "You are a NLHE 6-max poker decision engine.\n\n"
        "Rules:\n"
        "- Use only the provided information.\n"
        "- Do not invent values.\n"
        "- Choose only from available_actions.\n"
        "- action_label must match exactly one string from available_actions.\n"
        "- Return only valid JSON.\n\n"
        f"Table state:\n{json.dumps(state, ensure_ascii=True, indent=2)}\n\n"
        "Return JSON only:\n\n"
        '{"action_label":"","reason":""}'
    )


def _extract_json(text):
    if not text:
        return None

    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _match_action_by_label(table, action_label):
    normalized_target = (action_label or "").strip().lower()
    if not normalized_target:
        return None

    for action in table.available_actions:
        label = action.get("label", "")
        if label.strip().lower() == normalized_target:
            return action

    for action in table.available_actions:
        label = action.get("label", "")
        if normalized_target in label.strip().lower():
            return action

    return None


def choose_action_with_ollama(
    table,
    hero_equity=None,
    hero_position=None,
    big_blind=None,
    model=DEFAULT_OLLAMA_MODEL,
    timeout=45,
):
    if not table.available_actions:
        return {
            "selected_action": None,
            "reason": "Nessuna azione disponibile.",
            "raw_response": "",
        }

    prompt = build_ollama_prompt(
        table,
        hero_equity=hero_equity,
        hero_position=hero_position,
        big_blind=big_blind,
    )

    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )

    raw_response = (result.stdout or "").strip()
    parsed = _extract_json(raw_response)

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Errore durante la chiamata a ollama.")

    if parsed is None:
        raise ValueError(f"Risposta Ollama non parsabile: {raw_response}")

    selected_action = _match_action_by_label(table, parsed.get("action_label"))
    if selected_action is None:
        raise ValueError(f"Azione suggerita non valida: {parsed.get('action_label')}")

    return {
        "selected_action": selected_action,
        "reason": parsed.get("reason", ""),
        "raw_response": raw_response,
    }
