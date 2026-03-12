from poker.player import Player


class Table:
    """
    Classe che rappresenta il tavolo.
    Contiene:
    - lista giocatori
    - pot
    - carte comuni sul tavolo
    - carte dell'hero
    - street corrente della mano
    """

    VALID_STREETS = ("preflop", "flop", "turn", "river")

    def __init__(self, max_players=6, hero_seat=0):
        self.max_players = max_players
        self.hero_seat = hero_seat
        self.players = [Player(i) for i in range(max_players)]
        self.pot = 0.0
        self.board_cards = []
        self.hero_cards = []
        self.street = "preflop"

    def get_player(self, seat: int):
        return self.players[seat]

    def set_pot(self, pot: float):
        self.pot = pot

    def set_board_cards(self, cards):
        self.board_cards = list(cards or [])
        self.street = self._street_from_board()

    def set_hero_cards(self, cards):
        self.hero_cards = list(cards or [])

    def reset_hand_state(self):
        self.pot = 0.0
        self.board_cards.clear()
        self.hero_cards.clear()
        self.street = "preflop"

    def _street_from_board(self):
        board_len = len(self.board_cards)

        if board_len >= 5:
            return "river"
        if board_len == 4:
            return "turn"
        if board_len == 3:
            return "flop"
        return "preflop"
