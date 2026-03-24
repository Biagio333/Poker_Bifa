import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from treys import Card, Evaluator


_HAND_EVALUATOR = Evaluator()


@dataclass
class AdvisorProfileConfig:
    name: str = "cash_mixed"
    game_type: str = "cash"
    play_style: str = "mixed"

    short_stack_bb: float = 15.0
    medium_stack_bb: float = 40.0

    preflop_base_shift: float = 0.0
    preflop_open_shift: float = 0.0
    preflop_call_shift: float = 0.0
    preflop_3bet_shift: float = 0.0
    preflop_speculative_shift: float = 0.0
    preflop_short_stack_tightening: float = 0.0
    preflop_deep_stack_loosening: float = 0.0

    postflop_base_shift: float = 0.0
    postflop_raise_shift: float = 0.0
    postflop_call_shift: float = 0.0
    postflop_bluff_shift: float = 0.0
    postflop_draw_shift: float = 0.0
    postflop_thin_value_shift: float = 0.0

    tournament_survival_bias: float = 0.0
    cash_ev_bias: float = 0.0

    open_size_mult: float = 1.0
    iso_size_mult: float = 1.0
    raise_size_mult: float = 1.0
    postflop_bet_size_mult: float = 1.0


_PROFILE_LIBRARY = {
    "cash_aggressive": AdvisorProfileConfig(
        name="cash_aggressive",
        game_type="cash",
        play_style="aggressive",
        preflop_base_shift=0.03,
        preflop_open_shift=0.03,
        preflop_call_shift=-0.01,
        preflop_3bet_shift=-0.03,
        preflop_speculative_shift=0.03,
        preflop_deep_stack_loosening=0.03,
        postflop_base_shift=0.02,
        postflop_raise_shift=-0.04,
        postflop_call_shift=-0.01,
        postflop_bluff_shift=-0.05,
        postflop_draw_shift=-0.03,
        postflop_thin_value_shift=-0.03,
        cash_ev_bias=0.02,
        open_size_mult=1.05,
        iso_size_mult=1.05,
        raise_size_mult=1.08,
        postflop_bet_size_mult=1.08,
    ),
    "cash_conservative": AdvisorProfileConfig(
        name="cash_conservative",
        game_type="cash",
        play_style="conservative",
        preflop_base_shift=-0.03,
        preflop_open_shift=-0.02,
        preflop_call_shift=0.02,
        preflop_3bet_shift=0.04,
        preflop_speculative_shift=-0.03,
        preflop_short_stack_tightening=0.03,
        postflop_base_shift=-0.02,
        postflop_raise_shift=0.04,
        postflop_call_shift=0.02,
        postflop_bluff_shift=0.05,
        postflop_draw_shift=0.02,
        postflop_thin_value_shift=0.04,
        cash_ev_bias=-0.01,
        open_size_mult=0.97,
        iso_size_mult=0.98,
        raise_size_mult=0.95,
        postflop_bet_size_mult=0.95,
    ),
    "cash_mixed": AdvisorProfileConfig(
        name="cash_mixed",
        game_type="cash",
        play_style="mixed",
    ),
    "tournament_aggressive": AdvisorProfileConfig(
        name="tournament_aggressive",
        game_type="tournament",
        play_style="aggressive",
        short_stack_bb=18.0,
        medium_stack_bb=35.0,
        preflop_base_shift=0.02,
        preflop_open_shift=0.04,
        preflop_call_shift=0.02,
        preflop_3bet_shift=-0.02,
        preflop_speculative_shift=-0.01,
        preflop_short_stack_tightening=0.02,
        postflop_base_shift=0.01,
        postflop_raise_shift=-0.03,
        postflop_call_shift=0.01,
        postflop_bluff_shift=-0.03,
        postflop_draw_shift=-0.01,
        tournament_survival_bias=0.02,
        open_size_mult=1.00,
        iso_size_mult=1.00,
        raise_size_mult=1.03,
        postflop_bet_size_mult=1.02,
    ),
    "tournament_conservative": AdvisorProfileConfig(
        name="tournament_conservative",
        game_type="tournament",
        play_style="conservative",
        short_stack_bb=18.0,
        medium_stack_bb=35.0,
        preflop_base_shift=-0.04,
        preflop_open_shift=-0.03,
        preflop_call_shift=0.04,
        preflop_3bet_shift=0.05,
        preflop_speculative_shift=-0.05,
        preflop_short_stack_tightening=0.06,
        postflop_base_shift=-0.03,
        postflop_raise_shift=0.05,
        postflop_call_shift=0.03,
        postflop_bluff_shift=0.07,
        postflop_draw_shift=0.03,
        postflop_thin_value_shift=0.05,
        tournament_survival_bias=0.05,
        open_size_mult=0.95,
        iso_size_mult=0.95,
        raise_size_mult=0.94,
        postflop_bet_size_mult=0.94,
    ),
    "tournament_mixed": AdvisorProfileConfig(
        name="tournament_mixed",
        game_type="tournament",
        play_style="mixed",
        short_stack_bb=18.0,
        medium_stack_bb=35.0,
        tournament_survival_bias=0.02,
    ),
}


def get_advisor_profile(
    profile_name: Optional[str] = None,
    game_type: str = "cash",
    play_style: str = "mixed",
) -> AdvisorProfileConfig:
    if profile_name:
        return _PROFILE_LIBRARY.get(profile_name, _PROFILE_LIBRARY["cash_mixed"])

    key = f"{(game_type or 'cash').lower()}_{(play_style or 'mixed').lower()}"
    return _PROFILE_LIBRARY.get(key, _PROFILE_LIBRARY["cash_mixed"])


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


def _to_treys_card(card: str):
    if not isinstance(card, str) or len(card) < 2:
        return None
    rank = card[0].upper()
    suit = card[1].lower()
    if rank not in "23456789TJQKA" or suit not in "cdhs":
        return None
    try:
        return Card.new(rank + suit)
    except Exception:
        return None


def _postflop_hand_class(hero_cards, board_cards):
    hero = [_to_treys_card(card) for card in _hero_cards_normalized(hero_cards)]
    board = [_to_treys_card(card) for card in list(board_cards or [])]

    hero = [card for card in hero if card is not None]
    board = [card for card in board if card is not None]

    if len(hero) != 2 or len(board) < 3:
        return None

    try:
        score = _HAND_EVALUATOR.evaluate(board, hero)
        rank_class = _HAND_EVALUATOR.get_rank_class(score)
        return _HAND_EVALUATOR.class_to_string(rank_class)
    except Exception:
        return None


def _effective_bb_from_state(table_state: Dict) -> float:
    hero_stack = _safe_float(table_state.get("hero_stack", 0.0))
    villain_stack = _safe_float(table_state.get("villain_stack", 0.0))
    big_blind = max(_safe_float(table_state.get("big_blind", 1.0)), 1e-9)
    effective_stack = min(hero_stack, villain_stack) if villain_stack > 0 else hero_stack
    return effective_stack / big_blind


def _stack_zone(effective_bb: float, profile: AdvisorProfileConfig) -> str:
    if effective_bb <= profile.short_stack_bb:
        return "short"
    if effective_bb <= profile.medium_stack_bb:
        return "medium"
    return "deep"


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


def _preflop_raise_target(table_state, hand_category, hero_position, players_in_hand, effective_bb, profile=None):
    profile = profile or get_advisor_profile()

    big_blind = max(_safe_float(table_state.get("big_blind", 1.0)), 1e-9)
    to_call = _safe_float(table_state.get("to_call", 0.0))
    hero_bet = _safe_float(table_state.get("hero_bet", 0.0))
    current_price = hero_bet + to_call
    spot = _detect_preflop_spot(table_state)
    late_position = hero_position in {"btn", "co", "dealer"}
    blind_position = hero_position in {"sb", "bb"}

    if effective_bb <= 10:
        if hand_category == "premium":
            return max(current_price * 2.2, hero_bet + max(to_call, big_blind) * 2.2) * profile.raise_size_mult
        if hand_category == "strong":
            return max(current_price * 2.0, hero_bet + max(to_call, big_blind) * 2.0) * profile.raise_size_mult

    if spot == "free":
        open_bb = 2.3 if late_position else 2.7
        if blind_position:
            open_bb = 3.0
        if hand_category == "premium":
            open_bb += 0.3
        if players_in_hand > 2:
            open_bb += min(0.7, 0.2 * (players_in_hand - 2))
        return open_bb * big_blind * profile.open_size_mult

    if spot == "limped":
        limper_count = max(players_in_hand - 2, 1)
        iso_bb = 3.5 + (0.75 * limper_count)
        if late_position:
            iso_bb -= 0.5
        elif hand_category != "premium":
            iso_bb -= 0.2
        if hand_category == "premium":
            iso_bb += 0.3
        return iso_bb * big_blind * profile.iso_size_mult

    if spot in {"raised", "large_raise"}:
        if hand_category == "premium":
            multiplier = 2.4
        elif hand_category == "strong":
            multiplier = 2.0
        else:
            multiplier = 1.8

        if effective_bb <= 25 and hand_category == "premium":
            multiplier += 0.1

        return current_price * multiplier * profile.raise_size_mult

    return None


def _postflop_raise_target(table_state, decision_score, street, profile=None):
    profile = profile or get_advisor_profile()

    pot_size = _safe_float(table_state.get("pot_size", 0.0))
    to_call = _safe_float(table_state.get("to_call", 0.0))
    hero_bet = _safe_float(table_state.get("hero_bet", 0.0))
    min_raise = _safe_float(table_state.get("min_raise", 0.0))

    if pot_size <= 0 and min_raise > 0:
        return min_raise * profile.postflop_bet_size_mult

    if to_call <= 0:
        pot_fraction = 0.33
        if street == "turn":
            pot_fraction = 0.45
        elif street == "river":
            pot_fraction = 0.55
        if decision_score > 0.24:
            pot_fraction += 0.10
        return max(min_raise, pot_size * pot_fraction * profile.postflop_bet_size_mult)

    raise_to = hero_bet + to_call + max(to_call, pot_size * 0.33)
    if decision_score > 0.22:
        raise_to += pot_size * 0.15
    return max(min_raise, raise_to * profile.postflop_bet_size_mult)


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
    order = _rank_order()
    rank = (rank or "").upper()
    if rank not in order:
        return 0
    return order.index(rank) + 2


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


def _is_medium_pair(hero_cards) -> bool:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2 or not _is_pair(cards):
        return False
    rank = _rank_value(_card_rank(cards[0]))
    return 10 <= rank <= 13


def _is_tt_or_jj(hero_cards) -> bool:
    cards = _hero_cards_normalized(hero_cards)
    if len(cards) != 2 or not _is_pair(cards):
        return False
    rank = _card_rank(cards[0])
    return rank in {"T", "J"}


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
        if hi >= 14:
            return "premium"
        if hi >= 11:
            return "strong"
        if hi >= 8:
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
        return "raised"
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


def decide_preflop_action(table_state: Dict, advisor_profile: Optional[AdvisorProfileConfig] = None) -> Dict:
    advisor_profile = advisor_profile or get_advisor_profile()

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
    stack_zone = _stack_zone(effective_bb, advisor_profile)

    late_position = hero_position in {"btn", "co", "dealer"}
    blind_position = hero_position in {"sb", "bb"}
    suited = _is_suited(hero_cards)
    pair = _is_pair(hero_cards)
    ugly_offsuit = _is_trash_offsuit_preflop(hero_cards)
    protected_playable = _is_protected_playable_preflop(hero_cards)
    tt_or_jj = _is_tt_or_jj(hero_cards)

    score = {
        "premium": 0.30,
        "strong": 0.16,
        "medium": 0.05,
        "speculative": -0.01,
        "weak": -0.08,
        "trash": -0.18,
    }.get(hand_category, -0.18)

    score += advisor_profile.preflop_base_shift

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
        score -= 0.10

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
            score -= 0.03
        elif hand_category == "strong":
            score -= 0.01
        elif hand_category == "premium":
            score += 0.015

    if villain_type in {"nit", "tag"} and spot in {"raised", "large_raise"}:
        if hand_category in {"medium", "speculative"}:
            score -= 0.03
        elif tt_or_jj:
            score -= 0.05

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

    if tt_or_jj:
        if spot == "raised":
            score -= 0.03
        elif spot == "large_raise":
            score -= 0.08

        if effective_bb <= 18:
            score -= 0.04

    if hand_category == "speculative":
        score += advisor_profile.preflop_speculative_shift

    if stack_zone == "short":
        if hand_category in {"medium", "speculative", "weak"}:
            score -= advisor_profile.preflop_short_stack_tightening
        if advisor_profile.game_type == "tournament":
            score -= advisor_profile.tournament_survival_bias

    elif stack_zone == "deep":
        if hand_category in {"medium", "speculative"}:
            score += advisor_profile.preflop_deep_stack_loosening

    if advisor_profile.game_type == "cash":
        score += advisor_profile.cash_ev_bias

    if spot == "free":
        score += advisor_profile.preflop_open_shift
    elif spot in {"raised", "large_raise"}:
        score -= advisor_profile.preflop_3bet_shift
    elif spot == "limped":
        score -= advisor_profile.preflop_call_shift

    raise_kind = _raise_action_kind(available_kinds, "preflop")

    if hand_category == "premium":
        if spot in {"raised", "large_raise"} and effective_bb <= 12 and raise_kind:
            action = raise_kind
        elif raise_kind:
            action = raise_kind
        elif "call" in available_kinds:
            action = "call"
        else:
            action = "check" if "check" in available_kinds else "fold"

    elif hand_category == "strong":
        if tt_or_jj:
            if spot in {"free", "limped"} and raise_kind:
                action = raise_kind
            elif spot == "raised":
                if "call" in available_kinds:
                    action = "call"
                elif raise_kind and villain_type in {"lag", "aggressive", "maniac"} and effective_bb <= 14:
                    action = raise_kind
                else:
                    action = "fold" if "fold" in available_kinds else "check"
            elif spot == "large_raise":
                if effective_bb <= 10 and "call" in available_kinds:
                    action = "call"
                else:
                    action = "fold" if "fold" in available_kinds else "check"
            else:
                action = "call" if "call" in available_kinds else "check"
        else:
            if spot in {"free", "limped"} and raise_kind:
                action = raise_kind
            elif spot in {"raised", "large_raise"}:
                aggressive_3bet_threshold = 0.06 - advisor_profile.preflop_3bet_shift
                if score >= aggressive_3bet_threshold and raise_kind and villain_type not in {"calling_station", "passive_fish"} and effective_bb <= 20:
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
        elif spot == "raised" and score >= (0.02 - advisor_profile.preflop_call_shift) and "call" in available_kinds and effective_bb >= 25:
            action = "call"
        else:
            action = "fold" if "fold" in available_kinds else "check"

    elif hand_category == "speculative":
        if to_call <= 0 and "check" in available_kinds:
            action = "check"
        elif spot == "limped" and late_position and effective_bb >= 25 and "call" in available_kinds and score >= (-0.04 - advisor_profile.preflop_call_shift):
            action = "call"
        elif spot == "raised" and late_position and effective_bb >= 40 and suited and "call" in available_kinds and score >= (-0.02 - advisor_profile.preflop_call_shift):
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

    if protected_playable and action == "fold":
        if "call" in available_kinds:
            action = "call"
        elif "check" in available_kinds:
            action = "check"

    raise_target = None
    selected_amount_label = None
    if action in {"raise", "bet"} and amount_button_labels:
        raise_target = _preflop_raise_target(
            table_state,
            hand_category,
            hero_position,
            players_in_hand,
            effective_bb,
            advisor_profile,
        )
        selected_amount = _select_amount_button(
            [{"label": label} for label in amount_button_labels],
            raise_target,
            table_state,
        )
        selected_amount_label = selected_amount.get("label") if selected_amount else None

    confidence = _clamp(0.5 + abs(score) * 2.5, 0.0, 1.0)
    reason = (
        f"preflop category={hand_category} spot={spot} pos={hero_position or '?'} "
        f"eff_bb={effective_bb:.1f} villain={villain_type} players={players_in_hand} "
        f"profile={advisor_profile.name}"
    )

    return {
        "action": action,
        "confidence": round(confidence, 3),
        "reason": reason,
        "debug": {
            "street": "preflop",
            "advisor_profile": advisor_profile.name,
            "game_type": advisor_profile.game_type,
            "play_style": advisor_profile.play_style,
            "stack_zone": stack_zone,
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
            "tt_or_jj": tt_or_jj,
            "score": round(score, 4),
            "raise_target": round(raise_target, 4) if raise_target is not None else None,
            "selected_amount_label": selected_amount_label,
        },
    }


def _rank_to_value(rank: str) -> int:
    order = "23456789TJQKA"
    if not rank:
        return 0
    rank = rank.upper()
    if rank not in order:
        return 0
    return order.index(rank) + 2


def _card_rank_value(card: str) -> int:
    return _rank_to_value(_card_rank(card))


def _count_ranks(cards: List[str]) -> Dict[int, int]:
    counts = {}
    for card in cards or []:
        rv = _card_rank_value(card)
        if rv <= 0:
            continue
        counts[rv] = counts.get(rv, 0) + 1
    return counts


def _count_suits(cards: List[str]) -> Dict[str, int]:
    counts = {}
    for card in cards or []:
        s = _card_suit(card)
        if not s:
            continue
        counts[s] = counts.get(s, 0) + 1
    return counts


def _sorted_unique_rank_values(cards: List[str]) -> List[int]:
    vals = sorted({_card_rank_value(card) for card in cards or [] if _card_rank_value(card) > 0})
    if 14 in vals:
        vals = [1] + vals
    return vals


def _has_straight_draw(hero_cards: List[str], board_cards: List[str]) -> Dict[str, bool]:
    hero_cards = _hero_cards_normalized(hero_cards)
    board_cards = list(board_cards or [])

    if len(hero_cards) != 2 or len(board_cards) < 3:
        return {"open_ended": False, "gutshot": False}

    all_cards = hero_cards + board_cards
    vals = sorted(set(_card_rank_value(c) for c in all_cards if _card_rank_value(c) > 0))
    if 14 in vals:
        vals = [1] + vals

    hero_vals = set(_card_rank_value(c) for c in hero_cards if _card_rank_value(c) > 0)

    open_ended = False
    gutshot = False

    for start in range(1, 11):
        straight = {start, start + 1, start + 2, start + 3, start + 4}
        present = straight.intersection(vals)

        if len(present) != 4:
            continue

        if not (hero_vals & present):
            continue

        missing = list(straight - present)
        if len(missing) != 1:
            continue

        missing_rank = missing[0]
        if missing_rank in {start, start + 4}:
            open_ended = True
        else:
            gutshot = True

    return {
        "open_ended": open_ended,
        "gutshot": gutshot and not open_ended,
    }


def _has_flush_draw(hero_cards: List[str], board_cards: List[str]) -> bool:
    hero_cards = _hero_cards_normalized(hero_cards)
    board_cards = list(board_cards or [])

    if len(hero_cards) != 2 or len(board_cards) < 3:
        return False

    all_cards = hero_cards + board_cards
    suit_counts = _count_suits(all_cards)

    for suit, total_count in suit_counts.items():
        if total_count == 4:
            hero_count = sum(1 for c in hero_cards if _card_suit(c) == suit)
            if hero_count >= 1:
                return True

    return False


def _analyze_postflop_hand(hero_cards: List[str], board_cards: List[str]) -> Dict:
    hero_cards = _hero_cards_normalized(hero_cards)
    board_cards = list(board_cards or [])

    result = {
        "made_hand": None,
        "pair_type": None,
        "board_paired": False,
        "hero_pair_rank": 0,
        "top_board_rank": 0,
        "second_board_rank": 0,
        "third_board_rank": 0,
        "overcards_in_hand": 0,
        "flush_draw": False,
        "open_ended": False,
        "gutshot": False,
        "combo_draw": False,
        "strong_draw": False,
        "showdown_value": False,
        "hand_strength_bucket": "weak",
    }

    if len(hero_cards) != 2 or len(board_cards) < 3:
        return result

    all_cards = hero_cards + board_cards
    hero_rank_counts = _count_ranks(hero_cards)
    board_rank_counts = _count_ranks(board_cards)
    all_rank_counts = _count_ranks(all_cards)

    board_unique = sorted(board_rank_counts.keys(), reverse=True)
    result["top_board_rank"] = board_unique[0] if len(board_unique) > 0 else 0
    result["second_board_rank"] = board_unique[1] if len(board_unique) > 1 else 0
    result["third_board_rank"] = board_unique[2] if len(board_unique) > 2 else 0
    result["board_paired"] = any(v >= 2 for v in board_rank_counts.values())

    hero_ranks = [_card_rank_value(c) for c in hero_cards]
    board_ranks = [_card_rank_value(c) for c in board_cards]
    top_board_rank = result["top_board_rank"]

    result["overcards_in_hand"] = sum(1 for rv in hero_ranks if rv > top_board_rank)

    class_name = _postflop_hand_class(hero_cards, board_cards)
    result["made_hand"] = class_name

    flush_draw = _has_flush_draw(hero_cards, board_cards)
    straight_draws = _has_straight_draw(hero_cards, board_cards)
    result["flush_draw"] = flush_draw
    result["open_ended"] = straight_draws["open_ended"]
    result["gutshot"] = straight_draws["gutshot"]
    result["combo_draw"] = flush_draw and (result["open_ended"] or result["gutshot"])
    result["strong_draw"] = flush_draw or result["open_ended"]

    hero_set = set(hero_ranks)
    board_set = set(board_ranks)

    board_pairs = sorted(
        [rank for rank, count in board_rank_counts.items() if count >= 2],
        reverse=True,
    )
    board_trips = sorted(
        [rank for rank, count in board_rank_counts.items() if count >= 3],
        reverse=True,
    )

    if class_name == "Two Pair" and len(board_pairs) >= 2:
        if not (hero_set & board_set):
            result["pair_type"] = "board_two_pair"
            result["hand_strength_bucket"] = "weak"
            result["showdown_value"] = True
            return result

    if class_name == "Three of a Kind" and board_trips:
        board_trip_rank = board_trips[0]
        if board_trip_rank not in hero_set:
            result["pair_type"] = "board_trips"
            result["hero_pair_rank"] = board_trip_rank
            result["hand_strength_bucket"] = "weak"
            result["showdown_value"] = True
            return result

    if class_name in {"Straight Flush", "Four of a Kind", "Full House", "Flush", "Straight"}:
        result["hand_strength_bucket"] = "monster"
        result["showdown_value"] = True
        return result

    if class_name == "Three of a Kind":
        trip_ranks = [rank for rank, count in all_rank_counts.items() if count >= 3]
        hero_pair_ranks = [rank for rank, count in hero_rank_counts.items() if count == 2]

        if hero_pair_ranks:
            result["pair_type"] = "set"
            result["hero_pair_rank"] = hero_pair_ranks[0]
            result["hand_strength_bucket"] = "monster"
        else:
            paired_hero_ranks = [rank for rank in hero_ranks if rank in board_rank_counts]
            if paired_hero_ranks:
                result["pair_type"] = "trips"
                result["hero_pair_rank"] = max(paired_hero_ranks)
                result["hand_strength_bucket"] = "strong"
            else:
                result["pair_type"] = "board_trips"
                result["hero_pair_rank"] = max(trip_ranks) if trip_ranks else 0
                result["hand_strength_bucket"] = "weak"

        result["showdown_value"] = True
        return result

    if class_name == "Two Pair":
        shared_pairs = hero_set.intersection(board_set)

        if len(shared_pairs) >= 2:
            result["pair_type"] = "top_two" if max(shared_pairs) == top_board_rank else "two_pair"
            result["hand_strength_bucket"] = "strong"
            result["showdown_value"] = True
            return result

        if len(hero_rank_counts) == 1:
            hero_pair_rank = next(iter(hero_rank_counts.keys()))
            result["hero_pair_rank"] = hero_pair_rank

            if board_pairs:
                board_pair_rank = board_pairs[0]
                if hero_pair_rank > board_pair_rank:
                    result["pair_type"] = "overpair_plus_board_pair"
                    result["hand_strength_bucket"] = "medium"
                else:
                    result["pair_type"] = "underpair_plus_board_pair"
                    result["hand_strength_bucket"] = "medium"
                result["showdown_value"] = True
                return result

        if len(shared_pairs) == 1:
            shared_rank = max(shared_pairs)
            result["hero_pair_rank"] = shared_rank

            if shared_rank == top_board_rank:
                result["pair_type"] = "top_two"
                result["hand_strength_bucket"] = "strong"
            elif shared_rank == result["second_board_rank"]:
                result["pair_type"] = "middle_two"
                result["hand_strength_bucket"] = "medium_strong"
            else:
                result["pair_type"] = "weak_two_pair"
                result["hand_strength_bucket"] = "medium"
            result["showdown_value"] = True
            return result

        result["pair_type"] = "two_pair"
        result["hand_strength_bucket"] = "medium"
        result["showdown_value"] = True
        return result

    if class_name == "Pair":
        pair_ranks = [rank for rank, count in all_rank_counts.items() if count >= 2]

        if len(hero_rank_counts) == 1:
            hero_pair_rank = next(iter(hero_rank_counts.keys()))
            result["hero_pair_rank"] = hero_pair_rank

            if any(count >= 2 for count in board_rank_counts.values()):
                result["pair_type"] = "board_pair"
                result["hand_strength_bucket"] = "weak"
                result["showdown_value"] = result["overcards_in_hand"] >= 1
                return result

            if hero_pair_rank > top_board_rank:
                result["pair_type"] = "overpair"
                result["hand_strength_bucket"] = "strong"
            elif hero_pair_rank == top_board_rank:
                result["pair_type"] = "top_pair"
                result["hand_strength_bucket"] = "medium_strong"
            elif hero_pair_rank >= result["second_board_rank"]:
                result["pair_type"] = "middle_pair"
                result["hand_strength_bucket"] = "medium"
            else:
                result["pair_type"] = "underpair"
                result["hand_strength_bucket"] = "medium"
            result["showdown_value"] = True
            return result

        paired_hero_ranks = [rank for rank in hero_ranks if rank in board_rank_counts]
        if paired_hero_ranks:
            hero_pair_rank = max(paired_hero_ranks)
            result["hero_pair_rank"] = hero_pair_rank

            if hero_pair_rank == top_board_rank:
                result["pair_type"] = "top_pair"
                result["hand_strength_bucket"] = "medium_strong"
            elif hero_pair_rank == result["second_board_rank"]:
                result["pair_type"] = "middle_pair"
                result["hand_strength_bucket"] = "medium"
            else:
                result["pair_type"] = "bottom_pair"
                result["hand_strength_bucket"] = "medium"
            result["showdown_value"] = True
            return result

        if pair_ranks:
            result["pair_type"] = "board_pair"
            result["hand_strength_bucket"] = "weak"
            result["showdown_value"] = result["overcards_in_hand"] >= 1
            return result

    if class_name == "High Card":
        if result["combo_draw"]:
            result["hand_strength_bucket"] = "draw"
        elif result["strong_draw"]:
            result["hand_strength_bucket"] = "draw"
        elif result["gutshot"]:
            result["hand_strength_bucket"] = "draw"
        else:
            result["hand_strength_bucket"] = "weak"
        result["showdown_value"] = result["overcards_in_hand"] >= 1
        return result

    return result


def decide_postflop_action(table_state: Dict, advisor_profile: Optional[AdvisorProfileConfig] = None) -> Dict:
    advisor_profile = advisor_profile or get_advisor_profile()
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

    raw_edge = equity - required_equity

    sample_weight = _clamp(hands_seen / 40.0, 0.15, 1.0)
    effective_stack = min(hero_stack, villain_stack) if villain_stack > 0 else hero_stack
    spr = effective_stack / max(pot_size, big_blind, 1e-9)
    effective_bb = _effective_bb_from_state(table_state)
    stack_zone = _stack_zone(effective_bb, advisor_profile)

    bet_pressure = (
        villain_bet / max(pot_size, big_blind, 1e-9)
        if villain_bet > 0
        else to_call / max(pot_size, big_blind, 1e-9)
    )

    hand_analysis = _analyze_postflop_hand(
        table_state.get("hero_cards", []),
        table_state.get("board", []),
    )

    hand_class = hand_analysis["made_hand"]
    pair_type = hand_analysis["pair_type"]
    hand_strength_bucket = hand_analysis["hand_strength_bucket"]
    flush_draw = hand_analysis["flush_draw"]
    open_ended = hand_analysis["open_ended"]
    gutshot = hand_analysis["gutshot"]
    combo_draw = hand_analysis["combo_draw"]
    strong_draw = hand_analysis["strong_draw"]
    showdown_value = hand_analysis["showdown_value"]

    if pair_type in {"board_pair", "board_two_pair", "board_trips"}:
        hand_strength_bucket = "weak"

    exploit_adjustment = 0.0

    if hero_position in {"btn", "co", "dealer"}:
        exploit_adjustment += 0.01
    elif hero_position in {"sb", "bb", "utg", "mp"}:
        exploit_adjustment -= 0.01

    if players_in_hand > 2:
        exploit_adjustment -= min(0.05, 0.02 * (players_in_hand - 2))

    if villain_type == "nit":
        exploit_adjustment -= 0.02
        if aggression >= 2.0:
            exploit_adjustment -= 0.015
        if bet_pressure >= 0.60:
            exploit_adjustment -= 0.015

    if villain_type in {"lag", "aggressive", "maniac"}:
        exploit_adjustment += 0.01

    if aggression >= 2.5:
        exploit_adjustment += 0.01
    elif aggression >= 1.5:
        exploit_adjustment += 0.005

    if villain_type in {"calling_station", "passive_fish"}:
        if hand_strength_bucket in {"monster", "strong", "medium_strong"}:
            exploit_adjustment += 0.015
        else:
            exploit_adjustment -= 0.035

    if villain_type == "tag":
        exploit_adjustment -= 0.01

    if villain_type == "unknown":
        exploit_adjustment -= 0.005

    if street == "flop":
        if fold_to_cbet_pct >= 0.55 and _can_raise(available_kinds):
            exploit_adjustment += 0.01
        elif fold_to_cbet_pct <= 0.30:
            exploit_adjustment -= 0.01

    if _can_raise(available_kinds):
        if fold_to_raise_pct >= 0.60:
            exploit_adjustment += 0.015
        elif fold_to_raise_pct >= 0.45:
            exploit_adjustment += 0.008

    if strong_draw:
        exploit_adjustment += 0.015
    elif gutshot:
        exploit_adjustment += 0.005

    if combo_draw:
        exploit_adjustment += 0.015

    if spr < 2.5:
        if hand_strength_bucket in {"monster", "strong", "medium_strong"}:
            exploit_adjustment += 0.02
        elif strong_draw or combo_draw:
            exploit_adjustment += 0.01
        else:
            exploit_adjustment -= 0.005

    if min_raise > 0 and min_raise >= hero_stack * 0.35:
        exploit_adjustment -= 0.015

    if bet_pressure >= 0.75:
        exploit_adjustment -= 0.02
    elif bet_pressure >= 0.50:
        exploit_adjustment -= 0.01

    exploit_adjustment *= sample_weight
    exploit_adjustment = _clamp(exploit_adjustment, -0.10, 0.08)

    exploit_adjustment += advisor_profile.postflop_base_shift

    if hand_strength_bucket == "draw":
        exploit_adjustment -= advisor_profile.postflop_draw_shift

    if hand_strength_bucket in {"medium", "medium_strong"}:
        exploit_adjustment -= advisor_profile.postflop_thin_value_shift

    if advisor_profile.game_type == "tournament":
        if stack_zone == "short" and hand_strength_bucket in {"weak", "draw", "medium"}:
            exploit_adjustment -= advisor_profile.tournament_survival_bias

    if advisor_profile.game_type == "cash":
        exploit_adjustment += advisor_profile.cash_ev_bias

    decision_score = raw_edge + exploit_adjustment

    can_check = "check" in available_kinds
    can_call = "call" in available_kinds
    can_fold = "fold" in available_kinds
    can_raise = _can_raise(available_kinds)

    action_kind = None

    if to_call <= 0:
        if hand_strength_bucket == "monster":
            if can_raise:
                action_kind = _raise_action_kind(available_kinds, street) or "check"
            else:
                action_kind = "check" if can_check else ("call" if can_call else "fold")

        elif hand_strength_bucket == "strong":
            threshold = 0.10 + advisor_profile.postflop_raise_shift
            if street == "river":
                threshold += 0.03
            if villain_type in {"calling_station", "passive_fish"}:
                threshold -= 0.01

            if can_raise and decision_score > threshold:
                action_kind = _raise_action_kind(available_kinds, street) or "check"
            else:
                action_kind = "check" if can_check else ("call" if can_call else "fold")

        elif hand_strength_bucket == "medium_strong":
            threshold = 0.16 + advisor_profile.postflop_thin_value_shift
            if street == "turn":
                threshold += 0.02
            if street == "river":
                threshold += 0.05
            if villain_type in {"calling_station", "passive_fish"}:
                threshold += 0.02

            if can_raise and decision_score > threshold and equity >= 0.56:
                action_kind = _raise_action_kind(available_kinds, street) or "check"
            else:
                action_kind = "check" if can_check else ("call" if can_call else "fold")

        elif hand_strength_bucket == "medium":
            threshold = 0.24 + advisor_profile.postflop_thin_value_shift
            if pair_type == "top_pair":
                threshold -= 0.05
            elif pair_type == "middle_pair":
                threshold += 0.02
            elif pair_type in {"bottom_pair", "underpair"}:
                threshold += 0.05

            if street == "river":
                threshold += 0.05
            if villain_type in {"calling_station", "passive_fish"}:
                threshold += 0.04

            if can_raise and decision_score > threshold and equity >= 0.62 and players_in_hand <= 2:
                action_kind = _raise_action_kind(available_kinds, street) or "check"
            else:
                action_kind = "check" if can_check else ("call" if can_call else "fold")

        elif hand_strength_bucket == "draw":
            bluff_threshold = 0.20 + advisor_profile.postflop_bluff_shift
            if combo_draw:
                bluff_threshold -= 0.03
            elif open_ended:
                bluff_threshold -= 0.02
            elif gutshot:
                bluff_threshold += 0.03

            if street == "river":
                bluff_threshold += 0.10
            if players_in_hand > 2:
                bluff_threshold += 0.04
            if villain_type in {"calling_station", "passive_fish"}:
                bluff_threshold += 0.08
            if fold_to_raise_pct >= 0.60:
                bluff_threshold -= 0.03
            if fold_to_cbet_pct >= 0.60 and street == "flop":
                bluff_threshold -= 0.02

            if can_raise and decision_score > bluff_threshold:
                action_kind = _raise_action_kind(available_kinds, street) or "check"
            else:
                action_kind = "check" if can_check else ("call" if can_call else "fold")

        else:
            bluff_threshold = 0.30 + advisor_profile.postflop_bluff_shift
            if street == "turn":
                bluff_threshold += 0.03
            if street == "river":
                bluff_threshold += 0.10
            if players_in_hand > 2:
                bluff_threshold += 0.05
            if villain_type in {"calling_station", "passive_fish"}:
                bluff_threshold += 0.08
            if showdown_value:
                bluff_threshold += 0.05

            if can_raise and decision_score > bluff_threshold:
                action_kind = _raise_action_kind(available_kinds, street) or "check"
            else:
                action_kind = "check" if can_check else ("call" if can_call else "fold")

    else:
        if hand_strength_bucket == "monster":
            raise_threshold = 0.08 + advisor_profile.postflop_raise_shift
            if street == "river":
                raise_threshold += 0.03
            if villain_type in {"calling_station", "passive_fish"}:
                raise_threshold += 0.02

            if can_raise and decision_score > raise_threshold and equity >= 0.68:
                action_kind = _raise_action_kind(available_kinds, street)
                if action_kind is None:
                    action_kind = "call" if can_call else "check"
            elif can_call:
                action_kind = "call"
            else:
                action_kind = "fold" if can_fold else "check"

        elif hand_strength_bucket == "strong":
            raise_threshold = 0.14 + advisor_profile.postflop_raise_shift
            if street == "river":
                raise_threshold += 0.04
            if villain_type in {"calling_station", "passive_fish"}:
                raise_threshold += 0.04

            if can_raise and decision_score > raise_threshold and equity >= 0.62:
                action_kind = _raise_action_kind(available_kinds, street)
                if action_kind is None:
                    action_kind = "call" if can_call else "check"
            elif decision_score >= -0.02 and can_call:
                action_kind = "call"
            else:
                action_kind = "fold" if can_fold else ("check" if can_check else "call")

        elif hand_strength_bucket == "medium_strong":
            raise_threshold = 0.18 + advisor_profile.postflop_raise_shift
            if street == "river":
                raise_threshold += 0.04
            if villain_type in {"calling_station", "passive_fish"}:
                raise_threshold += 0.05

            if can_raise and decision_score > raise_threshold and equity >= 0.58:
                action_kind = _raise_action_kind(available_kinds, street)
                if action_kind is None:
                    action_kind = "call" if can_call else "check"
            elif decision_score >= -0.01 and can_call:
                action_kind = "call"
            else:
                action_kind = "fold" if can_fold else ("check" if can_check else "call")

        elif hand_strength_bucket == "medium":
            call_floor = -0.02 + advisor_profile.postflop_call_shift
            if pair_type == "top_pair":
                call_floor += 0.03
            elif pair_type == "middle_pair":
                call_floor += 0.01
            elif pair_type in {"bottom_pair", "underpair"}:
                call_floor -= 0.02

            if strong_draw or combo_draw:
                call_floor += 0.02
            elif gutshot:
                call_floor += 0.005

            if villain_type in {"calling_station", "passive_fish"}:
                call_floor -= 0.005

            if decision_score >= call_floor and can_call:
                action_kind = "call"
            else:
                action_kind = "fold" if can_fold else ("check" if can_check else "call")

        elif hand_strength_bucket == "draw":
            call_floor = 0.00 + advisor_profile.postflop_call_shift
            if combo_draw:
                call_floor -= 0.04
            elif open_ended or flush_draw:
                call_floor -= 0.02
            elif gutshot:
                call_floor += 0.02

            if bet_pressure >= 0.60:
                call_floor += 0.03

            semi_bluff_raise_threshold = 0.20 + advisor_profile.postflop_bluff_shift
            if combo_draw:
                semi_bluff_raise_threshold -= 0.03
            if villain_type in {"calling_station", "passive_fish"}:
                semi_bluff_raise_threshold += 0.05

            if can_raise and decision_score > semi_bluff_raise_threshold and combo_draw and players_in_hand <= 2:
                action_kind = _raise_action_kind(available_kinds, street)
                if action_kind is None:
                    action_kind = "call" if can_call else "check"
            elif decision_score >= call_floor and can_call:
                action_kind = "call"
            else:
                action_kind = "fold" if can_fold else ("check" if can_check else "call")

        else:
            if showdown_value and decision_score >= 0.03 and can_call and bet_pressure <= 0.35:
                action_kind = "call"
            else:
                action_kind = "fold" if can_fold else ("check" if can_check else "call")

    if action_kind in {"raise", "bet"}:
        if hand_strength_bucket == "weak":
            if to_call > 0:
                action_kind = "call" if can_call else ("check" if can_check else "fold")
            else:
                action_kind = "check" if can_check else ("call" if can_call else "fold")

        elif hand_strength_bucket == "medium":
            if street in {"turn", "river"} and equity < 0.68:
                if to_call > 0:
                    action_kind = "call" if can_call else ("check" if can_check else "fold")
                else:
                    action_kind = "check" if can_check else ("call" if can_call else "fold")

        elif hand_strength_bucket == "draw":
            if street == "river":
                action_kind = "check" if can_check else ("fold" if can_fold else "call")

    if street == "river" and action_kind in {"raise", "bet"}:
        if hand_strength_bucket in {"medium", "draw", "weak"}:
            if to_call > 0:
                action_kind = "call" if can_call else ("check" if can_check else "fold")
            elif can_check:
                action_kind = "check"

    raise_target = None
    selected_amount_label = None
    if action_kind in {"raise", "bet"} and amount_button_labels:
        raise_target = _postflop_raise_target(table_state, decision_score, street, advisor_profile)
        selected_amount = _select_amount_button(
            [{"label": label} for label in amount_button_labels],
            raise_target,
            table_state,
        )
        selected_amount_label = selected_amount.get("label") if selected_amount else None

    confidence = _clamp(0.5 + abs(decision_score) * 2.2, 0.0, 1.0)

    reason = (
        f"street={street} eq={equity:.2f} req={required_equity:.2f} "
        f"raw={raw_edge:+.2f} adj={exploit_adjustment:+.2f} score={decision_score:+.2f} "
        f"hand={hand_class} pair={pair_type} bucket={hand_strength_bucket} "
        f"draws=fd:{int(flush_draw)} oesd:{int(open_ended)} gs:{int(gutshot)} "
        f"villain={villain_type} profile={advisor_profile.name}"
    )

    return {
        "action": action_kind,
        "confidence": round(confidence, 3),
        "reason": reason,
        "debug": {
            "street": street,
            "advisor_profile": advisor_profile.name,
            "game_type": advisor_profile.game_type,
            "play_style": advisor_profile.play_style,
            "stack_zone": stack_zone,
            "effective_bb": round(effective_bb, 4),
            "equity": round(equity, 4),
            "required_equity": round(required_equity, 4),
            "raw_edge": round(raw_edge, 4),
            "exploit_adjustment": round(exploit_adjustment, 4),
            "decision_score": round(decision_score, 4),
            "hand_class": hand_class,
            "pair_type": pair_type,
            "hand_strength_bucket": hand_strength_bucket,
            "flush_draw": flush_draw,
            "open_ended": open_ended,
            "gutshot": gutshot,
            "combo_draw": combo_draw,
            "strong_draw": strong_draw,
            "showdown_value": showdown_value,
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


def decide_action(table_state: Dict, advisor_profile: Optional[AdvisorProfileConfig] = None) -> Dict:
    street = str(table_state.get("street", "preflop")).lower()
    advisor_profile = advisor_profile or get_advisor_profile()

    if street == "preflop":
        return decide_preflop_action(table_state, advisor_profile=advisor_profile)
    return decide_postflop_action(table_state, advisor_profile=advisor_profile)


def choose_action_with_rules(
    table,
    hero_equity=None,
    hero_position=None,
    big_blind=None,
    seat_to_position=None,
    active_seats=None,
    advisor_profile: Optional[AdvisorProfileConfig] = None,
    profile_name: Optional[str] = None,
    game_type: str = "cash",
    play_style: str = "mixed",
):
    if not table.available_actions:
        return {
            "selected_action": None,
            "selected_amount_button": None,
            "reason": "Nessuna azione disponibile.",
            "debug": {},
            "table_state": {},
            "advisor_profile": None,
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

    advisor_profile = advisor_profile or get_advisor_profile(
        profile_name=profile_name,
        game_type=game_type,
        play_style=play_style,
    )

    decision = decide_action(table_state, advisor_profile=advisor_profile)
    selected_action = _find_action(table.available_actions, decision["action"])

    protected_playable = (
        str(table_state.get("street", "")).lower() == "preflop"
        and _is_protected_playable_preflop(table_state.get("hero_cards", []))
    )

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
        "advisor_profile": advisor_profile.name,
    }