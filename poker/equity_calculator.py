import random
from treys import Evaluator, Card


class PokerEquityCalculator:
    """
    Calcola l'equity di una mano di poker Texas Hold'em usando treys.

    Esempi:
        calc = PokerEquityCalculator()

        # Hero noto vs villain sconosciuto loose, flop
        equities = calc.calculate_equity(
            player_hands=[['As', 'Kh'], []],
            board_cards=['Qs', 'Js', '2d'],
            iterations=10000,
            player_types=['tight', 'loose']
        )

        print(equities)

        # Due mani note, turn
        equities = calc.calculate_equity(
            player_hands=[['As', 'Ah'], ['Kc', 'Kd']],
            board_cards=['2s', '7h', 'Tc', 'Jd'],
            iterations=20000
        )
        print(equities)
    """

    def __init__(self):
        self.evaluator = Evaluator()
        self.valid_player_types = {"tight", "loose", "aggressive", "passive"}
        self.valid_ranks = set("23456789TJQKA")
        self.valid_suits = set("cdhs")

    # =========================================================
    # UTIL
    # =========================================================
    def card_to_treys(self, card):
        """Converte una carta stringa tipo 'As' in formato treys."""
        return Card.new(card)

    def normalize_player_type(self, player_type):
        normalized = (player_type or "loose").strip().lower()
        if normalized not in self.valid_player_types:
            return "loose"
        return normalized

    def _normalize_player_types(self, player_hands, player_types=None):
        player_types = player_types or []
        normalized_types = []

        for i in range(len(player_hands)):
            raw_type = player_types[i] if i < len(player_types) else "loose"
            normalized_types.append(self.normalize_player_type(raw_type))

        return normalized_types

    def _is_valid_card(self, card):
        
        return (
            isinstance(card, str)
            and len(card) == 2
            and card[0] in self.valid_ranks
            and card[1] in self.valid_suits
        )

    def _validate_inputs(self, player_hands, board_cards):
        if not isinstance(player_hands, list):
            raise ValueError("player_hands deve essere una lista.")
        if not isinstance(board_cards, list):
            raise ValueError("board_cards deve essere una lista.")
        if len(board_cards) > 5:
            raise ValueError("Il board non può avere più di 5 carte.")
        if len(player_hands) < 2:
            raise ValueError("Servono almeno 2 giocatori.")

        all_cards = []

        for c in board_cards:
            if not self._is_valid_card(c):
                raise ValueError(f"Carta board non valida: {c}")
            all_cards.append(c)

        for i, hand in enumerate(player_hands):
            if hand is None:
                hand = []
            if not isinstance(hand, list):
                raise ValueError(f"La mano del giocatore {i} deve essere una lista.")
            if len(hand) > 2:
                raise ValueError(f"La mano del giocatore {i} non può avere più di 2 carte.")
            for c in hand:
                if not self._is_valid_card(c):
                    raise ValueError(f"Carta mano non valida nel giocatore {i}: {c}")
                all_cards.append(c)

        if len(all_cards) != len(set(all_cards)):
            raise ValueError("Ci sono carte duplicate tra board e mani.")

    def _build_available_deck(self, player_hands, board_cards):
        known_cards = set(board_cards)
        for hand in player_hands:
            known_cards.update(hand or [])

        full_deck = [rank + suit for rank in "23456789TJQKA" for suit in "cdhs"]
        return [card for card in full_deck if card not in known_cards]

    def _rank_value(self, rank):
        return "23456789TJQKA".index(rank) + 2

    # =========================================================
    # PROFILO MANI
    # =========================================================
    def _hand_profile_score(self, hand):
        """
        Score semplice per preferire mani più forti.
        Non è un vero range GTO, ma una euristica utile.
        """
        if len(hand) != 2:
            return 0

        r1, s1 = hand[0][0], hand[0][1]
        r2, s2 = hand[1][0], hand[1][1]

        high = max(self._rank_value(r1), self._rank_value(r2))
        low = min(self._rank_value(r1), self._rank_value(r2))
        is_pair = (r1 == r2)
        is_suited = (s1 == s2)
        gap = abs(high - low)
        broadway_count = sum(r in "TJQKA" for r in (r1, r2))

        score = high + low

        if is_pair:
            score += 28 + high

        if is_suited:
            score += 4

        if gap == 1:
            score += 5
        elif gap == 2:
            score += 2
        elif gap >= 4:
            score -= 4

        score += broadway_count * 4

        return score

    def _hand_matches_player_type(self, hand, player_type):
        score = self._hand_profile_score(hand)
        player_type = self.normalize_player_type(player_type)

        if player_type == "tight":
            return score >= 34

        if player_type == "aggressive":
            return score >= 28

        if player_type == "passive":
            return score >= 22

        # loose
        return True

    def _draw_hand_for_type(self, deck, player_type):
        """Estrae 2 carte casuali dal deck cercando di rispettare il profilo."""
        if len(deck) < 2:
            return []

        max_attempts = min(300, len(deck) * len(deck))

        for _ in range(max_attempts):
            hand = random.sample(deck, 2)
            if self._hand_matches_player_type(hand, player_type):
                return hand

        return random.sample(deck, 2)

    def _draw_second_card_for_partial_hand(self, known_card, deck, player_type):
        """Completa una mano da 1 carta cercando di rispettare il profilo del giocatore."""
        if not deck:
            return None

        shuffled = deck[:]
        random.shuffle(shuffled)

        max_attempts = min(200, len(shuffled))
        for i in range(max_attempts):
            candidate = shuffled[i]
            hand = [known_card, candidate]
            if self._hand_matches_player_type(hand, player_type):
                return candidate

        return random.choice(shuffled)

    # =========================================================
    # COMPLETAMENTO MANI
    # =========================================================
    def _complete_player_hands(self, player_hands, board_cards, player_types):
        """
        Completa le mani mancanti dei giocatori usando il deck disponibile.
        """
        deck = self._build_available_deck(player_hands, board_cards)
        completed_hands = []

        for i, hand in enumerate(player_hands):
            current_hand = list(hand or [])

            if len(current_hand) == 2:
                completed_hands.append(current_hand[:2])
                continue

            # Mano completamente sconosciuta
            if len(current_hand) == 0:
                sampled_hand = self._draw_hand_for_type(deck, player_types[i])
                if len(sampled_hand) != 2:
                    completed_hands.append(current_hand)
                    continue

                for c in sampled_hand:
                    deck.remove(c)

                completed_hands.append(sampled_hand)
                continue

            # Mano con 1 sola carta nota
            if len(current_hand) == 1:
                available = [c for c in deck if c != current_hand[0]]
                chosen = self._draw_second_card_for_partial_hand(
                    current_hand[0],
                    available,
                    player_types[i]
                )

                if chosen is None:
                    completed_hands.append(current_hand)
                    continue

                deck.remove(chosen)
                current_hand.append(chosen)
                completed_hands.append(current_hand)
                continue

            completed_hands.append(current_hand)

        return completed_hands

    # =========================================================
    # API PUBBLICA
    # =========================================================
    def calculate_equity(self, player_hands, board_cards, iterations=10000, player_types=None):
        """
        Calcola l'equity dei giocatori.

        Args:
            player_hands: lista di mani, es:
                [['As', 'Kc'], ['Qh', 'Jd']]
                oppure [['As', 'Kc'], []]
                oppure [['As'], []]
            board_cards: lista board, es:
                ['Th', '9s', '8d']
            iterations: numero simulazioni Monte Carlo
            player_types: lista profili, es:
                ['tight', 'loose']

        Returns:
            lista equity float per ogni giocatore
        """
        self._validate_inputs(player_hands, board_cards)
        player_types = self._normalize_player_types(player_hands, player_types)

        all_hands_complete = all(hand and len(hand) == 2 for hand in player_hands)

        # Caso board completo e tutte le hole cards note: risultato esatto
        if len(board_cards) == 5 and all_hands_complete:
            treys_hands = [[self.card_to_treys(card) for card in hand] for hand in player_hands]
            treys_board = [self.card_to_treys(card) for card in board_cards]

            scores = [self.evaluator.evaluate(treys_board, hand) for hand in treys_hands]
            min_score = min(scores)
            winners = [i for i, score in enumerate(scores) if score == min_score]

            return [
                (1.0 / len(winners)) if i in winners else 0.0
                for i in range(len(player_hands))
            ]

        return self._monte_carlo_equity(
            player_hands=player_hands,
            board_cards=board_cards,
            iterations=iterations,
            player_types=player_types
        )

    # =========================================================
    # MONTE CARLO
    # =========================================================
    def _monte_carlo_equity(self, player_hands, board_cards, iterations, player_types):
        wins = [0.0] * len(player_hands)
        valid_iterations = 0

        for _ in range(iterations):
            simulated_hands = self._complete_player_hands(player_hands, board_cards, player_types)

            if not all(len(hand) == 2 for hand in simulated_hands):
                continue

            deck = self._build_available_deck(simulated_hands, board_cards)
            random.shuffle(deck)

            current_board = board_cards.copy()
            cards_needed = 5 - len(current_board)

            if cards_needed < 0:
                continue

            if len(deck) < cards_needed:
                continue

            current_board.extend(deck[:cards_needed])

            try:
                treys_hands = [
                    [self.card_to_treys(card) for card in hand]
                    for hand in simulated_hands
                ]
                treys_board = [self.card_to_treys(card) for card in current_board]

                scores = [
                    self.evaluator.evaluate(treys_board, hand)
                    for hand in treys_hands
                ]

                min_score = min(scores)
                winners = [i for i, score in enumerate(scores) if score == min_score]

                for winner in winners:
                    wins[winner] += 1.0 / len(winners)

                valid_iterations += 1

            except Exception as e:
                print("Errore simulazione equity:", e)
                continue

        if valid_iterations == 0:
            return [0.0] * len(player_hands)

        return [w / valid_iterations for w in wins]


if __name__ == "__main__":
    calc = PokerEquityCalculator()

    # Esempio 1: hero noto vs villain sconosciuto
    equities = calc.calculate_equity(
        player_hands=[['As', 'Kh'], []],
        board_cards=['Qs', 'Js', '2d'],
        iterations=20000,
        player_types=['tight', 'loose']
    )
    print("Esempio 1:", equities)

    # Esempio 2: due mani note
    equities = calc.calculate_equity(
        player_hands=[['As', 'Ah'], ['Kc', 'Kd']],
        board_cards=['2s', '7h', 'Tc'],
        iterations=20000,
        player_types=['tight', 'tight']
    )
    print("Esempio 2:", equities)

    # Esempio 3: board completo, risultato esatto
    equities = calc.calculate_equity(
        player_hands=[['As', 'Ah'], ['Kc', 'Kd']],
        board_cards=['2s', '7h', 'Tc', 'Jd', '3c']
    )
    print("Esempio 3:", equities)
