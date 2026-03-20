import re
from difflib import SequenceMatcher


class Player:
    """
    Classe che rappresenta un giocatore al tavolo di poker.

    Contiene:
    - nome
    - stack
    - posizione al tavolo
    - stato nella mano
    - lista delle azioni
    - statistiche base
    """

    DEFAULT_STATS = {
        "hands_seen": 0,
        "vpip": 0,
        "pfr": 0,
        "bet": 0,
        "raise": 0,
        "call": 0,
        "check": 0,
        "fold": 0,
        "bet_flop": 0,
        "bet_turn": 0,
        "bet_river": 0,
        "raise_flop": 0,
        "raise_turn": 0,
        "raise_river": 0,
        "call_flop": 0,
        "call_turn": 0,
        "call_river": 0,
        "check_flop": 0,
        "check_turn": 0,
        "check_river": 0,
        "fold_flop": 0,
        "fold_turn": 0,
        "fold_river": 0,
        "three_bet_count": 0,
        "three_bet_opp": 0,
        "fold_to_cbet_count": 0,
        "fold_to_cbet_opp": 0,
        "fold_to_raise_count": 0,
        "fold_to_raise_opp": 0,
    }

    def __init__(self, seat: int):
        self.seat = seat
        self.name = "None"
        self._pending_name_change = None
        self.stack = 0.0
        self.current_bet = 0.0
        self.player_type = "loose"

        self.in_hand = True
        self.is_allin = False
        self.total_invested = 0.0
        self.total_hands = 0
        self.current_street = "preflop"
        self.current_street_old_frame = "preflop"


        self.amount_old = 0.0
        self.counter_new_insert = 0

        self.request_reset_hand = False
        self.action_old = None
        self.actions = []
        self.ocr_actions = []
        self.actions_by_street = {
            "preflop": [],
            "flop": [],
            "turn": [],
            "river": []
        }

        self.stats = self.DEFAULT_STATS.copy()
        self._stats_profile_name = None
        self._stats_dirty = False
        self._reset_hand_stat_flags()

    def _reset_hand_stat_flags(self):
        self._hand_seen_recorded = False
        self._hand_vpip_recorded = False
        self._hand_pfr_recorded = False
        self._hand_bet_recorded = False
        self._hand_raise_recorded = False
        self._hand_call_recorded = False
        self._hand_check_recorded = False
        self._hand_fold_recorded = False
        self._street_action_stat_flags = set()
        self._hand_three_bet_opp_recorded = False
        self._hand_three_bet_count_recorded = False
        self._hand_fold_to_cbet_opp_recorded = False
        self._hand_fold_to_cbet_count_recorded = False
        self._hand_fold_to_raise_opp_by_street = {}
        self._hand_fold_to_raise_count_by_street = {}

    def _increment_stat_once_per_hand(self, stat_name: str, flag_name: str):
        if getattr(self, flag_name):
            return
        self.stats[stat_name] += 1
        setattr(self, flag_name, True)
        self._stats_dirty = True

    def _increment_street_stat_once_per_hand(self, action: str, street: str):
        street = (street or "").strip().lower()
        if street not in {"flop", "turn", "river"}:
            return
        stat_name = f"{action}_{street}"
        if stat_name not in self.stats:
            return
        if stat_name in self._street_action_stat_flags:
            return
        self.stats[stat_name] += 1
        self._street_action_stat_flags.add(stat_name)
        self._stats_dirty = True

    def observe_current_hand(self):
        if self._hand_seen_recorded:
            return
        self.total_hands += 1
        self.stats["hands_seen"] += 1
        self._hand_seen_recorded = True
        self._stats_dirty = True

    def get_stats_profile_name(self):
        return self._stats_profile_name

    def needs_stats_load(self):
        normalized_name = (self.name or "").strip()
        return bool(normalized_name) and normalized_name != self._stats_profile_name

    def has_dirty_stats(self):
        return self._stats_dirty

    def mark_stats_saved(self):
        self._stats_dirty = False

    def export_stats(self):
        return self.stats.copy()

    def load_stats(self, stats: dict, profile_name: str):
        current_session_stats = self.stats.copy() if self._stats_profile_name is None else self.DEFAULT_STATS.copy()

        loaded_stats = self.DEFAULT_STATS.copy()
        for key in loaded_stats:
            loaded_stats[key] = int(stats.get(key, 0))

        self.stats = loaded_stats
        self.total_hands = self.stats["hands_seen"]
        self._stats_profile_name = profile_name
        self._stats_dirty = False

        for key, value in current_session_stats.items():
            if value:
                self.stats[key] += int(value)

        self.total_hands = self.stats["hands_seen"]
        if any(current_session_stats.values()):
            self._stats_dirty = True

    def get_stat_percentage(self, stat_name: str) -> float:
        hands_seen = self.stats.get("hands_seen", 0)
        if hands_seen <= 0:
            return 0.0
        return (self.stats.get(stat_name, 0) / hands_seen) * 100.0

    def get_fold_to_raise_percentage(self) -> float:
        opportunities = self.stats.get("fold_to_raise_opp", 0)
        if opportunities <= 5:
            return 0.0
        return (self.stats.get("fold_to_raise_count", 0) / opportunities) * 100.0

    def _is_facing_raise(self, street: str) -> bool:
        table = getattr(self, "table", None)
        if table is None:
            return False
        return table.has_prior_raise_on_street(street)

    def _record_fold_to_raise_stats(self, street: str, action: str):
        if action not in {"call", "fold"}:
            return
        if not self._is_facing_raise(street):
            return

        if not self._hand_fold_to_raise_opp_by_street.get(street):
            self.stats["fold_to_raise_opp"] += 1
            self._hand_fold_to_raise_opp_by_street[street] = True
            self._stats_dirty = True

        if action == "fold" and not self._hand_fold_to_raise_count_by_street.get(street):
            self.stats["fold_to_raise_count"] += 1
            self._hand_fold_to_raise_count_by_street[street] = True
            self._stats_dirty = True

    def _record_three_bet_stats(self, street: str, action: str):
        if street != "preflop" or action not in {"call", "fold", "raise"}:
            return
        table = getattr(self, "table", None)
        if table is None:
            return
        if table.count_prior_raises_on_street(street) != 1:
            return

        if not self._hand_three_bet_opp_recorded:
            self.stats["three_bet_opp"] += 1
            self._hand_three_bet_opp_recorded = True
            self._stats_dirty = True

        if action == "raise" and not self._hand_three_bet_count_recorded:
            self.stats["three_bet_count"] += 1
            self._hand_three_bet_count_recorded = True
            self._stats_dirty = True

    def _record_fold_to_cbet_stats(self, street: str, action: str):
        if street != "flop" or action not in {"call", "fold", "raise"}:
            return
        table = getattr(self, "table", None)
        if table is None:
            return
        if not table.is_facing_flop_cbet(self):
            return

        if not self._hand_fold_to_cbet_opp_recorded:
            self.stats["fold_to_cbet_opp"] += 1
            self._hand_fold_to_cbet_opp_recorded = True
            self._stats_dirty = True

        if action == "fold" and not self._hand_fold_to_cbet_count_recorded:
            self.stats["fold_to_cbet_count"] += 1
            self._hand_fold_to_cbet_count_recorded = True
            self._stats_dirty = True

    def classify_player(self) -> str:
        hands = self.stats.get("hands_seen", 0)
        vpip = self.stats.get("vpip", 0)
        pfr = self.stats.get("pfr", 0)
        call = self.stats.get("call", 0)
        bet = self.stats.get("bet", 0)
        raise_ = self.stats.get("raise", 0)

        if hands < 10:
            self.player_type = "unknown"
            return self.player_type

        vpip_pct = vpip / hands
        pfr_pct = pfr / hands

        # Aggression factor
        calls = max(call, 1)
        aggression = (bet + raise_) / calls

        # ------------------------------------------------
        # MANIAC
        # ------------------------------------------------
        if vpip_pct > 0.40 and pfr_pct > 0.30 and aggression >= 2:
            self.player_type = "maniac"
            return self.player_type

        # ------------------------------------------------
        # LAG (loose aggressive)
        # ------------------------------------------------
        if vpip_pct > 0.30 and pfr_pct > 0.20 and aggression >= 1:
            self.player_type = "lag"
            return self.player_type

        # ------------------------------------------------
        # TAG (tight aggressive)
        # ------------------------------------------------
        if 0.15 <= vpip_pct <= 0.25 and pfr_pct >= 0.12 and aggression >= 1:
            self.player_type = "tag"
            return self.player_type

        # ------------------------------------------------
        # NIT
        # ------------------------------------------------
        if vpip_pct < 0.15 and pfr_pct < 0.10:
            self.player_type = "nit"
            return self.player_type

        # ------------------------------------------------
        # CALLING STATION
        # ------------------------------------------------
        if vpip_pct > 0.30 and pfr_pct < 0.10 and aggression < 1:
            self.player_type = "calling_station"
            return self.player_type

        # ------------------------------------------------
        # PASSIVE FISH
        # ------------------------------------------------
        if vpip_pct > 0.25 and aggression < 0.7:
            self.player_type = "passive_fish"
            return self.player_type

        # ------------------------------------------------
        # LOOSE GENERICO
        # ------------------------------------------------
        if vpip_pct > 0.25:
            self.player_type = "loose"
            return self.player_type

        # Default
        self.player_type = "tag"
        return self.player_type

    def set_name(self, name: str, *, can_record_action: bool = True):
        normalized = (name or "").strip()
        if not normalized:
            return
        
        if normalized ==  'Vinto 1,27':
            normalized =normalized

        action_data = self._extract_action_from_text(normalized)

        if action_data is not None:
            # fronte salita azione (prende solo il primo)
            if self.action_old == action_data["action"]:
                    return None
            self.action_old = action_data["action"]

            self.register_ocr_action(
                action_data["action"],
                raw_text=normalized,
                amount=action_data["amount"],
                record_in_street=can_record_action,
            )
            self.counter_new_insert = 0
            return

        if normalized.startswith("Tempo")or normalized.startswith("tempo"):
            return
        
        previous_name = (self.name or "").strip() if self.name else ""
        if previous_name and normalized != previous_name :
            # Se OCR è molto simile, consideriamo il nome invariato.
            if self._name_similarity(previous_name, normalized) >= 0.90:
                return
            self._pending_name_change = {
                "seat": self.seat,
                "old_name": previous_name,
                "new_name": normalized,
            }

            if len(normalized) >= 3 and self.request_reset_hand==False:
                self.name = normalized

    def _name_similarity(self, old_name: str, new_name: str) -> float:
        a = (old_name or "").strip().lower()
        b = (new_name or "").strip().lower()
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _extract_action_from_text(self, text: str):
        if self.request_reset_hand==True:
            return None
        lowered = (text or "").strip().lower()
        compact = lowered.replace("-", " ")

        token_map = {
            "chiama": "call",
            "mettisb": "call",
            "mettibb": "call",
            "metti sb": "call",
            "metti bb": "call",
            "call": "call",
            "calls": "call",
            "vinto": "win",
            "passa": "fold",
            "fold": "fold",
            "check": "check",
            "puntata": "raise",
            "bet": "bet",
            "rilancia": "raise",
            "raise": "raise",
            "all-in": "allin",
            "all in": "allin",
            "Muck": "fold",
            "muck": "fold",
        }

        detected_action = None
        for token, action in token_map.items():
            normalized_token = token.lower()
            if re.search(rf"\b{re.escape(normalized_token)}", compact):
                detected_action = action
                break

        if detected_action is None:
            self.action_old = None
            return None
        

        
        amount_match = re.search(r"\d+(?:[\.,]\d+)?", compact)
        amount = self.current_bet 
        if amount_match:
            amount = float(amount_match.group(0).replace(",", "."))

        return {"action": detected_action, "amount": amount}

    def register_ocr_action(self, action: str, raw_text: str, amount: float = 0.0, *, record_in_street: bool = True):
        self.ocr_actions.append({
            "action": action,
            "raw_text": raw_text,
            "amount": amount,
        })
        # Registra in actions_by_street solo quando consentito dal chiamante.
        if record_in_street:
            self.add_action(self.current_street_old_frame, action, amount)

    def get_ocr_actions(self):
        return self.ocr_actions

    def consume_name_change(self):
        change = self._pending_name_change
        self._pending_name_change = None
        return change

    def update_stack(self, stack: float):
        self.stack = stack

    def update_current_bet(self, amount: float):
        self.current_bet = amount

    def set_player_type(self, player_type: str):
        normalized = (player_type or "loose").strip().lower()
        if normalized not in {"tight", "loose", "aggressive", "passive"}:
            normalized = "loose"
        self.player_type = normalized

    def new_hand(self):
        self.in_hand = True
        self.is_allin = False
        self.total_invested = 0.0
        self.current_bet = 0.0
        self.amount_old = 0.0
        self.current_street = "preflop"

        self.actions.clear()
        self.ocr_actions.clear()

        for street in self.actions_by_street:
            self.actions_by_street[street].clear()
        self._reset_hand_stat_flags()



    def get_total_hands(self):
        return self.total_hands

    def add_action(self, street: str, action: str, amount: float = 0):

        if action == "win":
            self.request_reset_hand=True
            self.counter_new_insert = 0

        street = (street or "preflop").strip().lower()
        if street not in self.actions_by_street:
            street = "preflop"

        amount = round(amount, 2 )# Evita di registrare azioni duplicate con stesso tipo e importo

        if action == "check" or action == "fold":
            amount = 0.0
            self.amount_old = 0.0  # reset amount_old per check/fold, non vogliamo che influenzi le azioni future

        #if self.actions_by_street[street]:
        #    last = self.actions_by_street[street][-1]
        #    same_action = last.get("action") == action
        #    same_amount = abs(float(last.get("amount", 0.0)) - float(amount)) < 1e-6
        #    if same_action and same_amount:
        #        return
        
        if self.counter_new_insert > 0:
            self.counter_new_insert -= 1
            return
        self.counter_new_insert = 2
        
        

        calculed_amount = amount - self.amount_old
        event = {
            "street": street,
            "action": action,
            "amount": calculed_amount
        }

        if action == "call" or action == "raise" or action == "bet":
            if calculed_amount == 0.0:
                self.amount_old = amount
                return

        self._record_fold_to_raise_stats(street, action)
        self._record_three_bet_stats(street, action)
        self._record_fold_to_cbet_stats(street, action)

        self.amount_old = amount
        self.actions.append(event)
        self.actions_by_street[street].append(event)
        

        if amount > 0:
            self.total_invested += calculed_amount

        self.observe_current_hand()

        if action == "fold":
            self.in_hand = False
            self._increment_stat_once_per_hand("fold", "_hand_fold_recorded")
            self._increment_street_stat_once_per_hand("fold", street)

        elif action == "call":
            self._increment_stat_once_per_hand("call", "_hand_call_recorded")
            if street == "preflop":
                self._increment_stat_once_per_hand("vpip", "_hand_vpip_recorded")
            else:
                self._increment_street_stat_once_per_hand("call", street)

        elif action == "check":
            self._increment_stat_once_per_hand("check", "_hand_check_recorded")
            self._increment_street_stat_once_per_hand("check", street)

        elif action == "bet":
            self._increment_stat_once_per_hand("bet", "_hand_bet_recorded")
            self._increment_street_stat_once_per_hand("bet", street)

        elif action == "raise":
            self._increment_stat_once_per_hand("raise", "_hand_raise_recorded")
            if street == "preflop":
                self._increment_stat_once_per_hand("vpip", "_hand_vpip_recorded")
                self._increment_stat_once_per_hand("pfr", "_hand_pfr_recorded")
            else:
                self._increment_street_stat_once_per_hand("raise", street)

    def get_actions(self):
        return self.actions

    def get_actions_street(self, street: str):
        return self.actions_by_street.get(street, [])

    def __str__(self):
        lines = [
            f"Seat {self.seat} | {self.name} | stack={self.stack:.2f} | bet={self.current_bet:.2f}"
            f" | type={self.player_type} | street={self.current_street}"
            f" | in_hand={self.in_hand} | allin={self.is_allin} | invested={self.total_invested:.2f}",
        ]
        lines.append(f"  Stats: {self.stats}")
        for street, acts in self.actions_by_street.items():
            if acts:
                acts_str = ", ".join(
                    f"{a['action']}({a['amount']:.2f})" if a['amount'] else a['action']
                    for a in acts
                )
                lines.append(f"  [{street}] {acts_str}")
        if self.ocr_actions:
            ocr_str = ", ".join(
                f"{a['action']}({a['amount']:.2f}) [{a['raw_text']}]" if a['amount'] else f"{a['action']} [{a['raw_text']}]"
                for a in self.ocr_actions
            )
            lines.append(f"  OCR actions: {ocr_str}")
        return "\n".join(lines)
