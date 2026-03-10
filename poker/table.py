from poker.player import Player


class Table:
    """
    Classe che rappresenta il tavolo.
    Contiene:
    - lista giocatori
    - pot
    """

    def __init__(self, max_players=6, hero_seat=0):
        self.max_players = max_players
        self.hero_seat = hero_seat
        self.players = [Player(i) for i in range(max_players)]
        self.pot = 0.0

    def get_player(self, seat: int):
        return self.players[seat]

    def set_pot(self, pot: float):
        self.pot = pot