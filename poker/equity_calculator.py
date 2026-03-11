import random
from treys import Evaluator, Card

class PokerEquityCalculator:
    """
    Calcola l'equity usando treys (libreria Python ottimizzata per poker)
    """

    def __init__(self):
        self.evaluator = Evaluator()

    def card_to_treys(self, card):
        """Converte carta da formato 'As' a formato treys"""
        rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        suit_map = {'c': 1, 'd': 2, 'h': 3, 's': 4}

        rank = card[0]
        suit = card[1]

        return Card.new(rank_map.get(rank, 14), suit_map.get(suit, 1))

    def calculate_equity(self, player_hands, board_cards, iterations=10000):
        """
        Calcola l'equity usando treys

        Args:
            player_hands: Lista di liste, es. [['As', 'Kc'], ['Qh', 'Jd']]
            board_cards: Lista delle carte del board, es. ['Th', '9s', '8d']
            iterations: Numero di simulazioni

        Returns:
            Lista delle equity per ogni giocatore (0.0-1.0)
        """
        if not player_hands:
            return []

        # Se board completo (5 carte), usa calcolo esatto
        if len(board_cards) == 5:
            try:
                # Converti carte
                treys_hands = []
                for hand in player_hands:
                    treys_hand = [self.card_to_treys(card) for card in hand]
                    treys_hands.append(treys_hand)

                treys_board = [self.card_to_treys(card) for card in board_cards]

                # Valuta ogni mano
                scores = []
                for hand in treys_hands:
                    score = self.evaluator.evaluate(treys_board, hand)
                    scores.append(score)

                # Determina vincitore (score più basso vince in treys)
                min_score = min(scores)
                winners = [i for i, score in enumerate(scores) if score == min_score]

                # Calcola equity
                equities = []
                for i in range(len(player_hands)):
                    if i in winners:
                        equity = 1.0 / len(winners)  # Split se pareggio
                    else:
                        equity = 0.0
                    equities.append(equity)

                return equities
            except:
                pass

        # Se board incompleto, usa Monte Carlo
        return self._monte_carlo_equity(player_hands, board_cards, iterations)

    def _monte_carlo_equity(self, player_hands, board_cards, iterations):
        """Calcolo Monte Carlo per board incompleto"""
        # Crea mazzo completo
        deck = []
        for suit in 'cdhs':
            for rank in '23456789TJQKA':
                card = rank + suit
                # Escludi carte già note
                known_cards = []
                for hand in player_hands:
                    known_cards.extend(hand)
                known_cards.extend(board_cards)

                if card not in known_cards:
                    deck.append(card)

        wins = [0] * len(player_hands)

        for _ in range(iterations):
            # Mescola e completa il board
            random.shuffle(deck)
            current_board = board_cards.copy()
            cards_needed = 5 - len(board_cards)
            current_board.extend(deck[:cards_needed])

            # Converti e valuta
            try:
                treys_hands = [[self.card_to_treys(card) for card in hand] for hand in player_hands]
                treys_board = [self.card_to_treys(card) for card in current_board]

                scores = []
                for hand in treys_hands:
                    score = self.evaluator.evaluate(treys_board, hand)
                    scores.append(score)

                # Determina vincitore
                min_score = min(scores)
                winners = [i for i, score in enumerate(scores) if score == min_score]

                for winner in winners:
                    wins[winner] += 1.0 / len(winners)  # Split equity
            except:
                continue

        # Calcola equity finale
        equities = [wins[i] / iterations for i in range(len(player_hands))]
        return equities