import re
from typing import Dict, List


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, low, high):
    return max(low, min(high, value))


def _pct(count, total):
    if total <= 0:
        return 0.0
    return count / total


def _normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _extract_amount(text):
    matches = re.findall(r"\d+(?:[\.,]\d+)?", text or "")
    if not matches:
        return None
    return float(matches[-1].replace(",", "."))


def _amount_button_target_value(label, table_state: Dict):
    normalized = _normalize_text(label)
    pot_size = _safe_float(table_state.get("pot_size", 0.0))
    big_blind = max(_safe_float(table_state.get("big_blind", 1.0)), 1e-9)
    min_raise = _safe_float(table_state.get("min_raise", 0.0))
    hero_stack = _safe_float(table_state.get("hero_stack", 0.0))
    villain_stack = _safe_float(table_state.get("villain_stack", 0.0))
    effective_stack = min(hero_stack, villain_stack) if villain_stack > 0 else hero_stack
    amount = _extract_amount(normalized)

    if normalized == "min" or "minim" in normalized:
        return min_raise if min_raise > 0 else None
    if normalized == "max" or "massim" in normalized:
        return effective_stack if effective_stack > 0 else hero_stack or None
    if "piatto" in normalized or "pot" in normalized:
        return pot_size if pot_size > 0 else None
    if "half" in normalized or "meta" in normalized:
        return pot_size * 0.5 if pot_size > 0 else None
    if "terz" in normalized:
        return pot_size * (1.0 / 3.0) if pot_size > 0 else None

    if amount is not None:
        if "/" in normalized:
            fraction_match = re.search(r"(\d+)\s*/\s*(\d+)", normalized)
            if fraction_match and pot_size > 0:
                numerator = float(fraction_match.group(1))
                denominator = max(float(fraction_match.group(2)), 1.0)
                return pot_size * (numerator / denominator)
        if any(token in normalized for token in ("bb", "blind", "bui")):
            return amount * big_blind
        if "x" in normalized and min_raise > 0:
            return amount * min_raise
        return amount

    if "all" in normalized:
        return effective_stack if effective_stack > 0 else hero_stack or None
    return None


def _select_amount_button(amount_buttons, target_amount, table_state: Dict):
    if not amount_buttons or target_amount is None or target_amount <= 0:
        return None

    best_button = None
    best_distance = None
    best_value = None

    for button in amount_buttons:
        value = _amount_button_target_value(button.get("label", ""), table_state)
        if value is None:
            continue
        distance = abs(value - target_amount)
        if best_distance is None or distance < best_distance or (
            abs(distance - best_distance) < 1e-9 and (best_value is None or value < best_value)
        ):
            best_button = button
            best_distance = distance
            best_value = value

    return best_button


def _preflop_raise_target(table_state, hand_category, hero_position, players_in_hand, effective_bb):
    big_blind = max(_safe_float(table_state.get("big_blind", 1.0)), 1e-9)
    to_call = _safe_float(table_state.get("to_call", 0.0))
    hero_bet = _safe_float(table_state.get("hero_bet", 0.0))
    current_price = hero_bet + to_call
    spot = _detect_preflop_spot(table_state)
    late_position = hero_position in {"btn", "co", "dealer"}
    blind_position = hero_position in {"sb", "bb"}

    if effective_bb <= 12 and hand_category in {"premium", "strong"}:
        return max(current_price * 2.0, hero_bet + max(to_call, big_blind) * 2.0)

    if spot == "free":
        open_bb = 2.3 if late_position else 2.7
        if blind_position:
            open_bb = 3.0
        if hand_category == "premium":
            open_bb += 0.3
        if players_in_hand > 2:
            open_bb += min(0.7, 0.2 * (players_in_hand - 2))
        return open_bb * big_blind

    if spot == "limped":
        limper_count = max(players_in_hand - 2, 1)
        iso_bb = 3.5 + (0.75 * limper_count)
        if late_position:
            iso_bb -= 0.5
        elif hand_category != "premium":
            iso_bb -= 0.2
        if hand_category == "premium":
            iso_bb += 0.3
        return iso_bb * big_blind

    if spot in {"open_raise", "reraise", "jam_or_huge_raise", "raised", "large_raise"}:
        if hand_category == "premium":
            multiplier = 2.5
        elif hand_category == "strong":
            multiplier = 2.2
        else:
            multiplier = 2.0
        if effective_bb <= 25:
            multiplier += 0.1
        return current_price * multiplier

    return None


def _postflop_raise_target(table_state, decision_score, street):
    pot_size = _safe_float(table_state.get("pot_size", 0.0))
    to_call = _safe_float(table_state.get("to_call", 0.0))
    hero_bet = _safe_float(table_state.get("hero_bet", 0.0))
    min_raise = _safe_float(table_state.get("min_raise", 0.0))

    if pot_size <= 0 and min_raise > 0:
        return min_raise

    if to_call <= 0:
        pot_fraction = 0.33
        if street == "turn":
            pot_fraction = 0.45
        elif street == "river":
            pot_fraction = 0.55
        if decision_score > 0.24:
            pot_fraction += 0.10
        return max(min_raise, pot_size * pot_fraction)

    raise_to = hero_bet + to_call + max(to_call, pot_size * 0.33)
    if decision_score > 0.22:
        raise_to += pot_size * 0.15
    return max(min_raise, raise_to)


def _rank_order() -> str:
    return "23456789TJQKA"


def _card_rank(card: str) -> str:
    if not card or len(card) < 2:
        return ""
    return card[0].upper()


def _card_suit(card: str) -> str:
    if not card or len(card) < 2:
        return ""
    return card[1].lower()


def _hero_cards_normalized(hero_cards) -> List[str]:
    if not isinstance(hero_cards, (list, tuple)) or len(hero_cards) != 2:
        return []
    cards = []
    for c in hero_cards:
        if isinstance(c, str) and len(c) >= 2:
            cards.append(c[:2])
    return cards if len(cards) == 2 else []


def _card_ranks(hero_cards: List[str]) -> List[str]:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2:
        return []
    order = _rank_order()
    ranks = [_card_rank(cards[0]), _card_rank(cards[1])]
    return sorted(ranks, key=lambda rank: order.index(rank), reverse=True)


def _rank_value(rank: str) -> int:
    return _rank_order().index(rank.upper()) + 2


def _is_pair(hero_cards) -> bool:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2:
        return False
    return _card_rank(cards[0]) == _card_rank(cards[1])


def _is_suited(hero_cards) -> bool:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2:
        return False
    return _card_suit(cards[0]) == _card_suit(cards[1])


def _is_offsuit(hero_cards) -> bool:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2:
        return False
    return _card_suit(cards[0]) != _card_suit(cards[1])


def _rank_values(hero_cards) -> List[int]:
    order = _rank_order()
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2:
        return []
    vals = []
    for c in cards:
        r = _card_rank(c)
        if r not in order:
            return []
        vals.append(order.index(r))
    return sorted(vals, reverse=True)


def _is_trash_offsuit_preflop(hero_cards) -> bool:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2 or _is_pair(cards) or _is_suited(cards):
        return False

    ranks = _card_ranks(cards)
    hi = _rank_value(ranks[0])
    lo = _rank_value(ranks[1])

    if hi <= 9 and lo <= 5:
        return True
    if hi == 10 and lo <= 4:
        return True
    if hi == 9 and lo <= 3:
        return True
    if hi == 8 and lo <= 4:
        return True
    if hi == 7 and lo <= 4:
        return True

    return False


def _preflop_hand_category(hero_cards: List[str]) -> str:
    """
    Categorie preflop:
    - premium
    - strong
    - medium
    - speculative
    - weak
    - trash

    Privilegia playability e struttura della mano, non la raw equity.
    """
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2:
        return "trash"

    ranks = _card_ranks(cards)
    hi = _rank_value(ranks[0])
    lo = _rank_value(ranks[1])
    pair = _is_pair(cards)
    suited = _is_suited(cards)
    gap = hi - lo
    broadway_count = sum(rank in "TJQKA" for rank in ranks)

    if _is_trash_offsuit_preflop(cards):
        return "trash"

    if pair:
        if hi >= 11:
            return "premium"
        if hi >= 8:
            return "strong"
        if hi >= 5:
            return "medium"
        return "speculative"

    if ranks == ["A", "K"]:
        return "premium"

    if suited and (ranks == ["K", "J"] or ranks == ["Q", "J"] or ranks == ["A", "J"] or ranks == ["A", "T"] or ranks == ["K", "Q"]):
        return "strong"

    if suited and ranks[0] == "A" and ranks[1] in {"Q", "J", "T", "9"}:
        return "strong"
    if suited and ranks[0] == "K" and ranks[1] in {"Q", "J", "T"}:
        return "strong"
    if suited and broadway_count == 2:
        return "strong"

    if broadway_count == 2 and ranks[0] in {"A", "K"}:
        return "medium"
    if suited and hi >= 11 and lo >= 9:
        return "medium"
    if suited and gap <= 2 and hi >= 9:
        return "speculative"
    if suited and hi >= 8 and lo >= 5:
        return "speculative"
    if hi >= 12 and lo >= 9:
        return "medium"
    if hi >= 11 and lo >= 8:
        return "speculative"

    if not suited and hi <= 10 and lo <= 6 and gap >= 3:
        return "trash"
    if not suited and hi <= 12 and lo <= 7:
        return "weak"

    if suited:
        return "weak"

    return "trash"


def _is_protected_playable_preflop(hero_cards: List[str]) -> bool:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2 or not _is_suited(cards):
        return False
    ranks = _card_ranks(cards)
    return ranks in (
        ["K", "J"],
        ["Q", "J"],
        ["A", "J"],
        ["A", "T"],
        ["K", "Q"],
    )


def _detect_preflop_spot(table_state: Dict) -> str:
    to_call = _safe_float(table_state.get("to_call", 0.0))
    big_blind = max(_safe_float(table_state.get("big_blind", 1.0)), 1e-9)

    if to_call <= 0:
        return "free"

    call_bb = to_call / big_blind

    if call_bb <= 1.0:
        return "limped"
    if call_bb <= 3.5:
        return "raised"        # 👈 open_raise trattato come raised
    if call_bb >= 6.0:
        return "large_raise"

    return "raised"


def _action_kind_from_label(label):
    normalized = _normalize_text(label)
    if any(token in normalized for token in ("passa", "fold", "muck")):
        return "fold"
    if "check" in normalized:
        return "check"
    if any(token in normalized for token in ("chiama", "call")):
        return "call"
    if any(token in normalized for token in ("rilancia", "raise")):
        return "raise"
    if any(token in normalized for token in ("punta", "bet")):
        return "bet"
    return None


def _find_action(table_actions, desired_kind):
    candidates = [
        action for action in table_actions
        if _action_kind_from_label(action.get("label", "")) == desired_kind
    ]
    if not candidates:
        return None

    if desired_kind in {"raise", "bet"}:
        def amount_key(action):
            amount = _extract_amount(action.get("label", ""))
            return float("inf") if amount is None else amount
        return min(candidates, key=amount_key)

    return candidates[0]


def _find_button_by_label(buttons, label):
    if not label:
        return None
    for button in buttons or []:
        if str(button.get("label", "")).strip().lower() == str(label).strip().lower():
            return button
    return None


def _normalize_active_seats(active_seats):
    if not active_seats:
        return None
    return {seat for seat in active_seats if isinstance(seat, int)}


def _player_is_active_in_hand(table, player, active_seats=None):
    if not player.in_hand:
        return False
    if active_seats is None:
        return True
    if player.seat == table.hero_seat:
        return True
    return player.seat in active_seats


def _iter_active_players(table, active_seats=None):
    normalized_active_seats = _normalize_active_seats(active_seats)
    return [
        player
        for player in table.players
        if _player_is_active_in_hand(table, player, normalized_active_seats)
    ]


def _count_in_hand_players(table, active_seats=None):
    return len(_iter_active_players(table, active_seats))


def _get_primary_villain(table, active_seats=None):
    opponents = [
        p for p in _iter_active_players(table, active_seats)
        if p.seat != table.hero_seat
    ]
    if not opponents:
        return None

    return max(
        opponents,
        key=lambda p: (
            _safe_float(p.current_bet),
            _safe_float(p.total_invested),
            _safe_float(p.stack),
        ),
    )


def _can_raise(available_kinds):
    return "raise" in available_kinds or "bet" in available_kinds


def _raise_action_kind(available_kinds, street):
    if street == "preflop" and "raise" in available_kinds:
        return "raise"
    if "bet" in available_kinds:
        return "bet"
    if "raise" in available_kinds:
        return "raise"
    return None


def build_table_state(table, hero_equity=None, hero_position=None, big_blind=None, villain=None, seat_to_position=None, active_seats=None):
    hero = table.get_player(table.hero_seat)
    active_players = _iter_active_players(table, active_seats)
    villain = villain or _get_primary_villain(table, active_seats)
    seat_to_position = seat_to_position or {}

    highest_bet = max(
        (_safe_float(player.current_bet) for player in active_players),
        default=0.0,
    )
    to_call = max(0.0, highest_bet - _safe_float(hero.current_bet))

    min_raise = 0.0
    raise_action = _find_action(table.available_actions, "raise") or _find_action(table.available_actions, "bet")
    if raise_action is not None:
        parsed_amount = _extract_amount(raise_action.get("label", ""))
        if parsed_amount is not None:
            min_raise = parsed_amount

    if min_raise <= 0.0:
        min_raise = max(big_blind or 0.0, to_call * 2.0)

    villain_stats = villain.export_stats() if villain is not None else {}

    return {
        "street": table.street,
        "hero_cards": list(table.hero_cards),
        "board": list(table.board_cards),
        "hero_position": hero_position or seat_to_position.get(table.hero_seat, ""),
        "hero_stack": _safe_float(hero.stack),
        "hero_bet": _safe_float(hero.current_bet),
        "pot_size": _safe_float(table.pot),
        "to_call": to_call,
        "min_raise": min_raise,
        "big_blind": _safe_float(big_blind, 1.0),
        "players_in_hand": _count_in_hand_players(table, active_seats),
        "available_actions": [action.get("label", "") for action in table.available_actions],
        "amount_button_labels": [button.get("label", "") for button in table.avaible_button],
        "monte_carlo_equity": _safe_float(hero_equity),
        "villain_position": seat_to_position.get(villain.seat, "") if villain is not None else "",
        "villain_stack": _safe_float(villain.stack) if villain is not None else 0.0,
        "villain_bet": _safe_float(villain.current_bet) if villain is not None else 0.0,
        "villain_type": villain.classify_player() if villain is not None else "unknown",
        "villain_stats": villain_stats,
    }


def decide_preflop_action(table_state: Dict) -> Dict:
    """
    Decisione preflop rule-based.
    NON usa la raw Monte Carlo equity come criterio dominante.
    """
    hero_cards = list(table_state.get("hero_cards", []))
    hero_position = str(table_state.get("hero_position", "")).lower()
    hero_stack = _safe_float(table_state.get("hero_stack", 0.0))
    villain_stack = _safe_float(table_state.get("villain_stack", 0.0))
    big_blind = max(_safe_float(table_state.get("big_blind", 1.0)), 1e-9)
    to_call = _safe_float(table_state.get("to_call", 0.0))
    players_in_hand = max(_safe_int(table_state.get("players_in_hand", 2)), 1)
    villain_type = str(table_state.get("villain_type", "unknown")).lower()

    available_action_labels = [str(label) for label in table_state.get("available_actions", [])]
    amount_button_labels = [str(label) for label in table_state.get("amount_button_labels", [])]
    available_kinds = {_action_kind_from_label(label) for label in available_action_labels}
    available_kinds.discard(None)

    hand_category = _preflop_hand_category(hero_cards)
    spot = _detect_preflop_spot(table_state)
    effective_bb = min(hero_stack, villain_stack) / big_blind if villain_stack > 0 else hero_stack / big_blind

    late_position = hero_position in {"btn", "co", "dealer"}
    blind_position = hero_position in {"sb", "bb"}
    suited = _is_suited(hero_cards)
    pair = _is_pair(hero_cards)
    ugly_offsuit = _is_trash_offsuit_preflop(hero_cards)
    protected_playable = _is_protected_playable_preflop(hero_cards)

    score = {
        "premium": 0.30,
        "strong": 0.18,
        "medium": 0.06,
        "speculative": -0.01,
        "weak": -0.08,
        "trash": -0.18,
    }.get(hand_category, -0.18)

    if late_position:
        score += 0.04
    elif blind_position:
        score -= 0.01
    else:
        score -= 0.02

    if spot == "free":
        score += 0.04
    elif spot == "limped":
        score += 0.015
    elif spot == "raised":
        score -= 0.03
    elif spot == "large_raise":
        score -= 0.08

    if players_in_hand > 2:
        if hand_category in {"premium", "strong"}:
            score += 0.01
        elif hand_category == "speculative" and effective_bb >= 35 and suited:
            score += 0.02
        else:
            score -= 0.02

    if effective_bb >= 60:
        if hand_category == "speculative":
            score += 0.035
        elif hand_category == "medium" and suited:
            score += 0.015
    elif effective_bb <= 20:
        if hand_category == "speculative":
            score -= 0.05
        elif hand_category == "medium":
            score -= 0.02
        elif hand_category in {"premium", "strong"}:
            score += 0.015

    if villain_type in {"nit", "tag"} and spot in {"raised", "large_raise"}:
        if hand_category in {"medium", "speculative"}:
            score -= 0.03

    if villain_type in {"lag", "aggressive", "maniac"} and spot in {"raised", "large_raise"}:
        if hand_category in {"strong", "medium"}:
            score += 0.02

    if villain_type in {"calling_station", "passive_fish"}:
        if hand_category in {"premium", "strong"}:
            score += 0.01
        elif hand_category in {"medium", "speculative", "weak"}:
            score -= 0.03

    if ugly_offsuit:
        score -= 0.05

    raise_kind = _raise_action_kind(available_kinds, "preflop")

    if hand_category == "premium":
        if raise_kind:
            action = raise_kind
        elif "call" in available_kinds:
            action = "call"
        else:
            action = "check" if "check" in available_kinds else "fold"

    elif hand_category == "strong":
        if spot in {"free", "limped"} and raise_kind:
            action = raise_kind
        elif spot in {"raised", "large_raise"}:
            if score >= 0.05 and raise_kind and villain_type not in {"calling_station", "passive_fish"}:
                action = raise_kind
            elif "call" in available_kinds:
                action = "call"
            else:
                action = "fold" if "fold" in available_kinds else "check"
        else:
            action = "call" if "call" in available_kinds else "check"

    elif hand_category == "medium":
        if spot in {"free", "limped"} and late_position and raise_kind and villain_type not in {"calling_station", "passive_fish"}:
            action = raise_kind
        elif to_call <= 0 and "check" in available_kinds:
            action = "check"
        elif spot == "limped" and "call" in available_kinds:
            action = "call"
        elif spot == "raised" and score >= 0.02 and "call" in available_kinds:
            action = "call"
        else:
            action = "fold" if "fold" in available_kinds else "check"

    elif hand_category == "speculative":
        if to_call <= 0 and "check" in available_kinds:
            action = "check"
        elif spot == "limped" and late_position and effective_bb >= 25 and "call" in available_kinds:
            action = "call"
        elif spot == "raised" and late_position and effective_bb >= 40 and suited and "call" in available_kinds:
            action = "call"
        else:
            action = "fold" if "fold" in available_kinds else "check"

    elif hand_category == "weak":
        if to_call <= 0 and "check" in available_kinds:
            action = "check"
        else:
            action = "fold" if "fold" in available_kinds else "check"

    else:
        if to_call <= 0 and "check" in available_kinds:
            action = "check"
        else:
            action = "fold" if "fold" in available_kinds else "check"

    # Protezione esplicita: suited broadway molto giocabili non devono
    # essere foldate preflop in spot standard solo per score/spot aggressivi.
    if protected_playable and action == "fold":
        if "call" in available_kinds:
            action = "call"
        elif "check" in available_kinds:
            action = "check"

    raise_target = None
    selected_amount_label = None
    if action in {"raise", "bet"} and amount_button_labels:
        raise_target = _preflop_raise_target(table_state, hand_category, hero_position, players_in_hand, effective_bb)
        selected_amount_label = _select_amount_button(
            [{"label": label} for label in amount_button_labels],
            raise_target,
            table_state,
        )
        selected_amount_label = selected_amount_label.get("label") if selected_amount_label else None

    confidence = _clamp(0.5 + abs(score) * 2.5, 0.0, 1.0)
    reason = (
        f"preflop category={hand_category} spot={spot} pos={hero_position or '?'} "
        f"eff_bb={effective_bb:.1f} villain={villain_type} players={players_in_hand}"
    )

    return {
        "action": action,
        "confidence": round(confidence, 3),
        "reason": reason,
        "debug": {
            "street": "preflop",
            "hand_category": hand_category,
            "spot": spot,
            "effective_bb": round(effective_bb, 4),
            "hero_position": hero_position,
            "players_in_hand": players_in_hand,
            "villain_type": villain_type,
            "suited": suited,
            "pair": pair,
            "ugly_offsuit": ugly_offsuit,
            "protected_playable": protected_playable,
            "score": round(score, 4),
            "raise_target": round(raise_target, 4) if raise_target is not None else None,
            "selected_amount_label": selected_amount_label,
        },
    }


def decide_postflop_action(table_state: Dict) -> Dict:
    """
    Mantiene la logica attuale: equity Monte Carlo + pot odds + exploit adjustment.
    """
    villain_stats = table_state.get("villain_stats", {}) or {}

    street = str(table_state.get("street", "preflop")).lower()
    hero_position = str(table_state.get("hero_position", "")).lower()
    hero_stack = _safe_float(table_state.get("hero_stack", 0.0))
    pot_size = _safe_float(table_state.get("pot_size", 0.0))
    to_call = _safe_float(table_state.get("to_call", 0.0))
    min_raise = _safe_float(table_state.get("min_raise", 0.0))
    big_blind = max(_safe_float(table_state.get("big_blind", 1.0)), 1e-9)
    players_in_hand = max(_safe_int(table_state.get("players_in_hand", 2)), 1)
    equity = _clamp(_safe_float(table_state.get("monte_carlo_equity", 0.0)), 0.0, 1.0)
    villain_type = str(table_state.get("villain_type", "unknown")).lower()
    villain_stack = _safe_float(table_state.get("villain_stack", 0.0))
    villain_bet = _safe_float(table_state.get("villain_bet", 0.0))

    available_action_labels = [str(label) for label in table_state.get("available_actions", [])]
    amount_button_labels = [str(label) for label in table_state.get("amount_button_labels", [])]
    available_kinds = {_action_kind_from_label(label) for label in available_action_labels}
    available_kinds.discard(None)

    hands_seen = _safe_int(villain_stats.get("hands_seen", 0))
    vpip = _safe_int(villain_stats.get("vpip", 0))
    pfr = _safe_int(villain_stats.get("pfr", 0))
    bet = _safe_int(villain_stats.get("bet", 0))
    raise_ = _safe_int(villain_stats.get("raise", 0))
    call = _safe_int(villain_stats.get("call", 0))
    fold = _safe_int(villain_stats.get("fold", 0))
    fold_to_raise_count = _safe_int(villain_stats.get("fold_to_raise_count", 0))
    fold_to_raise_opp = _safe_int(villain_stats.get("fold_to_raise_opp", 0))
    three_bet_count = _safe_int(villain_stats.get("three_bet_count", 0))
    three_bet_opp = _safe_int(villain_stats.get("three_bet_opp", 0))
    fold_to_cbet_count = _safe_int(villain_stats.get("fold_to_cbet_count", 0))
    fold_to_cbet_opp = _safe_int(villain_stats.get("fold_to_cbet_opp", 0))

    vpip_pct = _pct(vpip, hands_seen)
    pfr_pct = _pct(pfr, hands_seen)
    call_pct = _pct(call, hands_seen)
    fold_pct = _pct(fold, hands_seen)
    aggression = (bet + raise_) / max(call, 1)
    fold_to_raise_pct = _pct(fold_to_raise_count, fold_to_raise_opp)
    three_bet_pct = _pct(three_bet_count, three_bet_opp)
    fold_to_cbet_pct = _pct(fold_to_cbet_count, fold_to_cbet_opp)

    required_equity = 0.0
    if to_call > 0:
        required_equity = to_call / max(pot_size + to_call, 1e-9)

    sample_weight = _clamp(hands_seen / 40.0, 0.15, 1.0)
    effective_stack = min(hero_stack, villain_stack) if villain_stack > 0 else hero_stack
    spr = effective_stack / max(pot_size, big_blind, 1e-9)
    bet_pressure = villain_bet / max(pot_size, big_blind, 1e-9) if villain_bet > 0 else to_call / max(pot_size, big_blind, 1e-9)

    exploit_adjustment = 0.0

    if hero_position in {"btn", "co", "dealer"}:
        exploit_adjustment += 0.015
    elif hero_position in {"sb", "bb", "utg", "mp"}:
        exploit_adjustment -= 0.01

    if players_in_hand > 2:
        exploit_adjustment -= min(0.04, 0.015 * (players_in_hand - 2))

    if villain_type == "nit":
        exploit_adjustment -= 0.02
        if aggression >= 2.0:
            exploit_adjustment -= 0.015
        if bet_pressure >= 0.60:
            exploit_adjustment -= 0.02

    if villain_type in {"lag", "aggressive", "maniac"}:
        exploit_adjustment += 0.015

    if aggression >= 2.5:
        exploit_adjustment += 0.02
    elif aggression >= 1.5:
        exploit_adjustment += 0.01

    if _can_raise(available_kinds):
        if fold_to_raise_pct >= 0.60:
            exploit_adjustment += 0.02
        elif fold_to_raise_pct >= 0.45:
            exploit_adjustment += 0.01

    if villain_type == "calling_station":
        exploit_adjustment -= 0.03
    if villain_type == "passive_fish":
        exploit_adjustment -= 0.025
    if call_pct >= 0.30 and aggression < 1.0:
        exploit_adjustment -= 0.015

    if villain_type == "tag":
        exploit_adjustment -= 0.01
    if villain_type == "unknown":
        exploit_adjustment -= 0.005

    if street == "flop":
        if fold_to_cbet_pct >= 0.55 and _can_raise(available_kinds):
            exploit_adjustment += 0.015
        elif fold_to_cbet_pct <= 0.30:
            exploit_adjustment -= 0.01

    if spr < 2.5:
        exploit_adjustment += 0.01

    if min_raise > 0 and min_raise >= hero_stack * 0.35:
        exploit_adjustment -= 0.01

    exploit_adjustment *= sample_weight
    exploit_adjustment = _clamp(exploit_adjustment, -0.10, 0.08)

    decision_score = equity - required_equity + exploit_adjustment

    can_check = "check" in available_kinds
    can_call = "call" in available_kinds
    can_fold = "fold" in available_kinds
    can_raise = _can_raise(available_kinds)

    if to_call <= 0:
        raise_threshold = 0.16
        if street == "flop":
            raise_threshold += 0.03
        if players_in_hand > 2:
            raise_threshold += 0.02
        if street == "river":
            raise_threshold += 0.04

        if can_raise and decision_score > raise_threshold:
            action_kind = _raise_action_kind(available_kinds, street) or "check"
        else:
            if can_check:
                action_kind = "check"
            elif can_call:
                action_kind = "call"
            elif can_fold:
                action_kind = "fold"
            else:
                action_kind = next(iter(available_kinds), "check")
    else:
        if can_fold and decision_score < -0.015:
            action_kind = "fold"
        elif decision_score <= 0.09:
            if can_call:
                action_kind = "call"
            elif can_check:
                action_kind = "check"
            elif can_fold:
                action_kind = "fold"
            else:
                action_kind = next(iter(available_kinds), "check")
        else:
            raise_threshold = 0.15
            if street == "river":
                raise_threshold += 0.05
            elif street == "turn":
                raise_threshold += 0.02
            if villain_type in {"calling_station", "passive_fish"}:
                raise_threshold += 0.05
            elif villain_type in {"unknown", "tag", "nit"}:
                raise_threshold += 0.02

            if can_raise and decision_score > raise_threshold:
                action_kind = _raise_action_kind(available_kinds, street)
                if action_kind is None:
                    action_kind = "call" if can_call else "check"
            else:
                if can_call:
                    action_kind = "call"
                elif can_check:
                    action_kind = "check"
                elif can_fold:
                    action_kind = "fold"
                else:
                    action_kind = next(iter(available_kinds), "check")

    raise_target = None
    selected_amount_label = None
    if action_kind in {"raise", "bet"} and amount_button_labels:
        raise_target = _postflop_raise_target(table_state, decision_score, street)
        selected_amount_label = _select_amount_button(
            [{"label": label} for label in amount_button_labels],
            raise_target,
            table_state,
        )
        selected_amount_label = selected_amount_label.get("label") if selected_amount_label else None

    confidence = _clamp(0.5 + abs(decision_score) * 2.5, 0.0, 1.0)

    reason = (
        f"street={street} eq={equity:.2f} req={required_equity:.2f} "
        f"adj={exploit_adjustment:+.2f} score={decision_score:+.2f} "
        f"villain={villain_type} vpip={vpip_pct:.0%} pfr={pfr_pct:.0%} "
        f"agg={aggression:.2f} fvr={fold_to_raise_pct:.0%}"
    )

    return {
        "action": action_kind,
        "confidence": round(confidence, 3),
        "reason": reason,
        "debug": {
            "street": street,
            "equity": round(equity, 4),
            "required_equity": round(required_equity, 4),
            "exploit_adjustment": round(exploit_adjustment, 4),
            "decision_score": round(decision_score, 4),
            "vpip_pct": round(vpip_pct, 4),
            "pfr_pct": round(pfr_pct, 4),
            "call_pct": round(call_pct, 4),
            "fold_pct": round(fold_pct, 4),
            "aggression": round(aggression, 4),
            "fold_to_raise_pct": round(fold_to_raise_pct, 4),
            "three_bet_pct": round(three_bet_pct, 4),
            "fold_to_cbet_pct": round(fold_to_cbet_pct, 4),
            "sample_weight": round(sample_weight, 4),
            "spr": round(spr, 4),
            "bet_pressure": round(bet_pressure, 4),
            "raise_target": round(raise_target, 4) if raise_target is not None else None,
            "selected_amount_label": selected_amount_label,
        },
    }


def decide_action(table_state: Dict) -> Dict:
    street = str(table_state.get("street", "preflop")).lower()
    if street == "preflop":
        return decide_preflop_action(table_state)
    return decide_postflop_action(table_state)


def choose_action_with_rules(table, hero_equity=None, hero_position=None, big_blind=None, seat_to_position=None, active_seats=None):
    if not table.available_actions:
        return {
            "selected_action": None,
            "selected_amount_button": None,
            "reason": "Nessuna azione disponibile.",
            "debug": {},
            "table_state": {},
        }

    villain = _get_primary_villain(table, active_seats)
    table_state = build_table_state(
        table,
        hero_equity=hero_equity,
        hero_position=hero_position,
        big_blind=big_blind,
        villain=villain,
        seat_to_position=seat_to_position,
        active_seats=active_seats,
    )
    decision = decide_action(table_state)
    selected_action = _find_action(table.available_actions, decision["action"])

    protected_playable = (
        str(table_state.get("street", "")).lower() == "preflop"
        and _is_protected_playable_preflop(table_state.get("hero_cards", []))
    )

    # Guard rail finale: suited broadway molto giocabili non devono
    # trasformarsi in fold per colpa del mapping OCR / fallback.
    if (
        protected_playable
        and selected_action is not None
        and _action_kind_from_label(selected_action.get("label", "")) == "fold"
    ):
        selected_action = None

    if selected_action is None:
        if protected_playable:
            fallback_order = ("raise", "bet", "call", "check", "fold")
        elif decision["action"] in {"raise", "bet"}:
            fallback_order = ("raise", "bet", "call", "check", "fold")
        else:
            fallback_order = ("check", "call", "fold", "bet", "raise")

        for fallback_kind in fallback_order:
            selected_action = _find_action(table.available_actions, fallback_kind)
            if selected_action is not None:
                break

    selected_amount_button = None
    if selected_action is not None and decision["action"] in {"raise", "bet"}:
        selected_amount_button = _find_button_by_label(
            table.avaible_button,
            decision.get("debug", {}).get("selected_amount_label"),
        )

    return {
        "selected_action": selected_action,
        "selected_amount_button": selected_amount_button,
        "reason": decision["reason"],
        "debug": decision["debug"],
        "table_state": table_state,
    }
