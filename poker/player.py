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

    def __init__(self, seat: int):
        self.seat = seat
        self.name = None
        self._pending_name_change = None
        self.stack = 0.0
        self.current_bet = 0.0
        self.player_type = "loose"

        self.in_hand = True
        self.is_allin = False
        self.total_invested = 0.0
        self.total_hands = 0
        self.current_street = "preflop"
        self.current_street_old = "preflop"

        self.amount_old = 0.0
        self.counter_new_insert = 0

        self.request_reset_hand = False

        self.actions = []
        self.ocr_actions = []
        self.actions_by_street = {
            "preflop": [],
            "flop": [],
            "turn": [],
            "river": []
        }

        self.stats = {
            "hands_seen": 0,
            "vpip": 0,
            "pfr": 0,
            "bet": 0,
            "raise": 0,
            "call": 0,
            "fold": 0
        }

    def set_name(self, name: str, *, can_record_action: bool = True):
        normalized = (name or "").strip()
        if not normalized:
            return

        action_data = self._extract_action_from_text(normalized)
        if action_data is not None:
            self.register_ocr_action(
                action_data["action"],
                raw_text=normalized,
                amount=action_data["amount"],
                record_in_street=can_record_action,
            )
            self.counter_new_insert = 0
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
        if normalized.startswith("Tempo")or normalized.startswith("tempo"):
            return
        if len(normalized) >= 3:
            self.name = normalized

    def _name_similarity(self, old_name: str, new_name: str) -> float:
        a = (old_name or "").strip().lower()
        b = (new_name or "").strip().lower()
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _extract_action_from_text(self, text: str):
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
        }

        detected_action = None
        for token, action in token_map.items():
            normalized_token = token.lower()
            if re.search(rf"\b{re.escape(normalized_token)}", compact):
                detected_action = action
                break

        if detected_action is None:
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
            self.add_action(self.current_street, action, amount)

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
        self.current_street_old = ""
        self.actions.clear()
        self.ocr_actions.clear()

        for street in self.actions_by_street:
            self.actions_by_street[street].clear()



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

        if self.actions_by_street[street]:
            last = self.actions_by_street[street][-1]
            same_action = last.get("action") == action
            same_amount = abs(float(last.get("amount", 0.0)) - float(amount)) < 1e-6
            if same_action and same_amount:
                return
        
        if action == "check" or action == "fold":
            amount = 0.0
            self.amount_old = 0.0  # reset amount_old per check/fold, non vogliamo che influenzi le azioni future


            
        if self.current_street_old != street:
            self.current_street_old = street
            self.amount_old = 0.0


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

        self.amount_old = amount
        self.actions.append(event)
        self.actions_by_street[street].append(event)
        

        if amount > 0:
            self.total_invested += calculed_amount


        if action == "fold":
            self.in_hand = False
            self.stats["fold"] += 1

        elif action == "call":
            self.stats["call"] += 1
            if street == "preflop":
                self.stats["vpip"] += 1

        elif action == "bet":
            self.stats["bet"] += 1

        elif action == "raise":
            self.stats["raise"] += 1
            if street == "preflop":
                self.stats["vpip"] += 1
                self.stats["pfr"] += 1
        
        self.total_hands += 1
        self.stats["hands_seen"] += 1

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
