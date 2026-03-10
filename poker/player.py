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
        self.stack = 0.0

        self.in_hand = True
        self.is_allin = False
        self.total_invested = 0.0

        self.actions = []
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

    def set_name(self, name: str):
        self.name = name

    def update_stack(self, stack: float):
        self.stack = stack

    def new_hand(self):
        self.in_hand = True
        self.is_allin = False
        self.total_invested = 0.0
        self.actions.clear()

        for street in self.actions_by_street:
            self.actions_by_street[street].clear()

        self.stats["hands_seen"] += 1

    def add_action(self, street: str, action: str, amount: float = 0):
        event = {
            "street": street,
            "action": action,
            "amount": amount
        }

        self.actions.append(event)
        self.actions_by_street[street].append(event)

        if amount > 0:
            self.total_invested += amount

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

    def get_actions(self):
        return self.actions

    def get_actions_street(self, street: str):
        return self.actions_by_street.get(street, [])

    def __str__(self):
        return f"Seat {self.seat} | {self.name} | stack={self.stack}"