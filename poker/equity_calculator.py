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
        self.valid_player_types = {
            "tight",
            "loose",
            "aggressive",
            "passive",
            "unknown",
            "maniac",
            "lag",
            "tag",
            "nit",
            "calling_station",
            "passive_fish",
        }
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

        profile_map = {
            "unknown": "loose",
            "maniac": "aggressive",
            "lag": "aggressive",
            "tag": "tight",
            "nit": "tight",
            "calling_station": "passive",
            "passive_fish": "passive",
        }
        return profile_map.get(normalized, normalized)

    def _normalize_player_types(self, player_hands, player_types=None):
        player_types = player_types or []
        normalized_types = []

        for i in range(len(player_hands)):
            raw_type = player_types[i] if i < len(player_types) else "loose"
            normalized_types.append(self.normalize_player_type(raw_type))

        return normalized_types

    def _build_table_equity_inputs(self, table, seat_to_position, active_seats):
        hero = table.get_player(table.hero_seat)
        if len(table.hero_cards) != 2:
            return None

        active_players = [
            player
            for player in table.players
            if player.in_hand and (
                player.seat == table.hero_seat
                or player.seat in (active_seats or [])
            )
        ]
        if len(active_players) < 2:
            return None

        opponents = [
            player for player in active_players
            if player.seat != table.hero_seat
        ]
        if not opponents:
            return None

        player_hands = [table.hero_cards] + [[] for _ in opponents]
        player_types = [hero.classify_player()] + [
            player.classify_player() for player in opponents
        ]
        player_positions = [
            seat_to_position.get(table.hero_seat, "")
        ] + [
            seat_to_position.get(player.seat, "") for player in opponents
        ]

        return {
            "hero": hero,
            "opponents": opponents,
            "player_hands": player_hands,
            "player_types": player_types,
            "player_positions": player_positions,
        }

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

    def _normalize_position(self, position):
        normalized = (position or "").strip().upper()
        aliases = {
            "HJ": "MP",
            "LJ": "MP",
            "UTG+1": "MP",
            "DEALER": "BTN",
            "BUTTON": "BTN",
        }
        return aliases.get(normalized, normalized)

    def _get_range_text(self, player_type, player_position):
        raw_type = (player_type or "unknown").strip().lower()
        position = self._normalize_position(player_position)
        ranges_for_type = PLAYER_RANGES.get(raw_type) or PLAYER_RANGES.get("unknown", {})
        return ranges_for_type.get(position)

    def _ordered_ranks_and_suited(self, hand):
        r1, s1 = hand[0][0], hand[0][1]
        r2, s2 = hand[1][0], hand[1][1]
        if self._rank_value(r2) > self._rank_value(r1):
            r1, r2 = r2, r1
            s1, s2 = s2, s1
        return r1, r2, s1 == s2

    def _hand_matches_range_token(self, hand, token):
        token = (token or "").strip().upper()
        if not token:
            return False
        if token == "ANY":
            return True
        if len(hand) != 2:
            return False

        r1, r2, suited = self._ordered_ranks_and_suited(hand)

        if len(token) == 2 and token[0] == token[1]:
            return r1 == token[0] and r2 == token[1]

        if len(token) == 3 and token[0] == token[1] and token[2] == "+":
            return r1 == r2 and self._rank_value(r1) >= self._rank_value(token[0])

        if len(token) == 3 and token[2] in {"S", "O"}:
            token_suited = token[2] == "S"
            return r1 == token[0] and r2 == token[1] and suited == token_suited

        if len(token) == 4 and token[2] in {"S", "O"} and token[3] == "+":
            token_suited = token[2] == "S"
            return (
                r1 == token[0]
                and suited == token_suited
                and self._rank_value(r2) >= self._rank_value(token[1])
                and self._rank_value(r2) < self._rank_value(r1)
            )

        return False

    def _hand_matches_position_range(self, hand, player_type, player_position):
        range_text = self._get_range_text(player_type, player_position)
        if not range_text:
            return False

        tokens = [token.strip() for token in range_text.split(",") if token.strip()]
        return any(self._hand_matches_range_token(hand, token) for token in tokens)

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

    def _hand_matches_player_type(self, hand, player_type, player_position=None):
        if player_position and self._hand_matches_position_range(hand, player_type, player_position):
            return True

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

    def _draw_hand_for_type(self, deck, player_type, player_position=None):
        """Estrae 2 carte casuali dal deck cercando di rispettare il profilo."""
        if len(deck) < 2:
            return []

        max_attempts = min(300, len(deck) * len(deck))
        for _ in range(max_attempts):
            hand = random.sample(deck, 2)
            if self._hand_matches_player_type(hand, player_type, player_position):
                return hand

        valid_hands = []
        for i in range(len(deck) - 1):
            for j in range(i + 1, len(deck)):
                hand = [deck[i], deck[j]]
                if self._hand_matches_player_type(hand, player_type, player_position):
                    valid_hands.append(hand)

        if valid_hands:
            return random.choice(valid_hands)

        return random.sample(deck, 2)

    def _draw_second_card_for_partial_hand(self, known_card, deck, player_type, player_position=None):
        """Completa una mano da 1 carta cercando di rispettare il profilo del giocatore."""
        if not deck:
            return None

        shuffled = deck[:]
        random.shuffle(shuffled)

        max_attempts = min(200, len(shuffled))
        for i in range(max_attempts):
            candidate = shuffled[i]
            hand = [known_card, candidate]
            if self._hand_matches_player_type(hand, player_type, player_position):
                return candidate

        valid_candidates = []
        for candidate in deck:
            hand = [known_card, candidate]
            if self._hand_matches_player_type(hand, player_type, player_position):
                valid_candidates.append(candidate)

        if valid_candidates:
            return random.choice(valid_candidates)

        return random.choice(deck)

    # =========================================================
    # COMPLETAMENTO MANI
    # =========================================================
    def _complete_player_hands(self, player_hands, board_cards, player_types, player_positions):
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
                sampled_hand = self._draw_hand_for_type(deck, player_types[i], player_positions[i])
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
                    player_types[i],
                    player_positions[i],
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
    def calculate_equity(self, player_hands, board_cards, iterations=10000, player_types=None, player_positions=None):
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
        player_positions = player_positions or []
        player_positions = [
            self._normalize_position(player_positions[i]) if i < len(player_positions) else ""
            for i in range(len(player_hands))
        ]

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
            player_types=player_types,
            player_positions=player_positions,
        )

    def calculate_table_equity(self, table, seat_to_position, active_seats, iterations=1000):
        equity_inputs = self._build_table_equity_inputs(
            table,
            seat_to_position or {},
            active_seats or [],
        )
        if equity_inputs is None:
            return {
                "hero_equity": None,
                "equities": [],
                "opponents": [],
                "player_types": [],
                "player_positions": [],
            }

        equities = self.calculate_equity(
            player_hands=equity_inputs["player_hands"],
            board_cards=table.board_cards,
            iterations=iterations,
            player_types=equity_inputs["player_types"],
            player_positions=equity_inputs["player_positions"],
        )

        return {
            "hero_equity": equities[0] if equities else None,
            "equities": equities,
            "opponents": equity_inputs["opponents"],
            "player_types": equity_inputs["player_types"],
            "player_positions": equity_inputs["player_positions"],
        }

    # =========================================================
    # MONTE CARLO
    # =========================================================
    def _monte_carlo_equity(self, player_hands, board_cards, iterations, player_types, player_positions):
        wins = [0.0] * len(player_hands)
        valid_iterations = 0

        for _ in range(iterations):
            simulated_hands = self._complete_player_hands(
                player_hands,
                board_cards,
                player_types,
                player_positions,
            )

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


PLAYER_RANGES = {

    "nit": {
        "UTG": "88+,AQs+,AKo",
        "MP":  "77+,AJs+,AQo+,KQs",
        "CO":  "66+,ATs+,AQo+,KQs",
        "BTN": "55+,ATs+,AJo+,KQs",
        "SB":  "55+,ATs+,AJo+,KQs",
        "BB":  "55+,ATs+,AJo+,KQs",
    },

    "tight": {
        "UTG": "66+,ATs+,KQs,AQo+",
        "MP":  "55+,ATs+,KJs+,QJs,AQo+,KQo",
        "CO":  "44+,A8s+,KTs+,QTs+,JTs,ATo+,KQo",
        "BTN": "22+,A2s+,K9s+,Q9s+,J9s+,T9s,98s,87s,A9o+,KTo+,QTo+,JTo",
        "SB":  "22+,A2s+,K8s+,Q9s+,J9s+,T8s+,97s+,A8o+,KTo+,QTo+,JTo",
        "BB":  "22+,A2s+,K7s+,Q8s+,J8s+,T8s+,97s+,A8o+,KTo+,QTo+,JTo",
    },

    "tag": {
        "UTG": "55+,A2s+,KTs+,QTs+,JTs,T9s,ATo+,KQo",
        "MP":  "44+,A2s+,K9s+,QTs+,JTs,T9s,98s,ATo+,KJo+,QJo",
        "CO":  "22+,A2s+,K7s+,Q8s+,J8s+,T8s+,97s+,A9o+,KTo+,QTo+,JTo",
        "BTN": "22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,86s+,75s+,A2o+,K9o+,Q9o+,J9o+",
        "SB":  "22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,86s+,A2o+,K9o+,Q9o+,J9o+",
        "BB":  "22+,A2s+,K4s+,Q6s+,J7s+,T7s+,96s+,A2o+,K8o+,Q9o+,J9o+",
    },

    "lag": {
        "UTG": "44+,A2s+,K9s+,QTs+,JTs,T9s,98s,AJo+,KQo",
        "MP":  "33+,A2s+,K7s+,Q9s+,J9s+,T9s,98s,87s,A9o+,KTo+,QTo+,JTo",
        "CO":  "22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,86s+,75s+,A2o+,K9o+,Q9o+,J9o+",
        "BTN": "22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,86s+,75s+,64s+,54s,A2o+,K8o+,Q9o+,J9o+,T8o+",
        "SB":  "22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,86s+,75s+,64s+,A2o+,K8o+,Q9o+,J9o+,T8o+",
        "BB":  "22+,A2s+,K2s+,Q4s+,J6s+,T6s+,95s+,85s+,A2o+,K7o+,Q8o+,J8o+,T8o+",
    },

    "loose": {
        "UTG": "44+,A2s+,KTs+,QTs+,JTs,T9s,98s,AJo+,KQo",
        "MP":  "33+,A2s+,K9s+,QTs+,JTs,T9s,98s,87s,ATo+,KJo+,QJo",
        "CO":  "22+,A2s+,K7s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,A8o+,KTo+,QTo+,JTo",
        "BTN": "22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,86s+,75s+,64s+,54s,A2o+,K8o+,Q9o+,J9o+,T9o",
        "SB":  "22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,85s+,74s+,A2o+,K8o+,Q9o+,J9o+,T8o+",
        "BB":  "22+,A2s+,K2s+,Q4s+,J6s+,T6s+,95s+,A2o+,K7o+,Q8o+,J8o+,T8o+,98o",
    },

    "aggressive": {
        "UTG": "55+,A2s+,KTs+,QTs+,JTs,T9s,98s,ATo+,KQo",
        "MP":  "44+,A2s+,K9s+,QTs+,JTs,T9s,98s,87s,ATo+,KJo+,QJo",
        "CO":  "22+,A2s+,K7s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,A9o+,KTo+,QTo+,JTo",
        "BTN": "22+,A2s+,K4s+,Q6s+,J7s+,T7s+,96s+,86s+,75s+,64s+,A2o+,K8o+,Q9o+,J9o+,T8o+",
        "SB":  "22+,A2s+,K2s+,Q4s+,J6s+,T6s+,95s+,85s+,A2o+,K7o+,Q8o+,J8o+,T8o+",
        "BB":  "22+,A2s+,K2s+,Q2s+,J5s+,T5s+,94s+,A2o+,K6o+,Q7o+,J8o+,T8o+",
    },

    "maniac": {
        "UTG": "22+,A2s+,K7s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,A8o+,KTo+,QTo+,JTo",
        "MP":  "22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,86s+,75s+,A5o+,K9o+,Q9o+,J9o+",
        "CO":  "22+,A2s+,K3s+,Q5s+,J7s+,T7s+,96s+,86s+,75s+,64s+,54s,A2o+,K8o+,Q9o+,J9o+,T8o+",
        "BTN": "ANY",
        "SB":  "ANY",
        "BB":  "ANY",
    },

    "calling_station": {
        "UTG": "22+,A2s+,KTs+,QTs+,JTs,AJo+,KQo",
        "MP":  "22+,A2s+,K9s+,QTs+,JTs,T9s,AJo+,KJo+,QJo",
        "CO":  "22+,A2s+,K8s+,Q9s+,J9s+,T9s,98s,A9o+,KTo+,QTo+",
        "BTN": "22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,86s+,A2o+,K9o+,Q9o+,J9o+",
        "SB":  "22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,A2o+,K9o+,Q9o+,J9o+",
        "BB":  "22+,A2s+,K4s+,Q6s+,J7s+,T7s+,96s+,A2o+,K8o+,Q9o+,J9o+",
    },

    "passive": {
        "UTG": "77+,ATs+,KQs,AQo+",
        "MP":  "66+,ATs+,KJs+,QJs,AQo+,KQo",
        "CO":  "55+,A9s+,KTs+,QTs+,JTs,ATo+,KQo",
        "BTN": "33+,A2s+,KTs+,QTs+,JTs,T9s,98s,A9o+,KTo+,QTo+",
        "SB":  "33+,A2s+,K9s+,QTs+,JTs,A9o+,KTo+,QTo+",
        "BB":  "22+,A2s+,K8s+,Q9s+,J9s+,T8s+,A8o+,KTo+,QTo+",
    },

    "passive_fish": {
        "UTG": "22+,A2s+,K9s+,QTs+,JTs,AJo+,KQo",
        "MP":  "22+,A2s+,K8s+,Q9s+,J9s+,T9s,A9o+,KTo+,QTo+",
        "CO":  "22+,A2s+,K7s+,Q8s+,J8s+,T8s+,A8o+,KTo+,QTo+",
        "BTN": "22+,A2s+,K4s+,Q6s+,J7s+,T7s+,A2o+,K8o+,Q9o+,J9o+",
        "SB":  "22+,A2s+,K4s+,Q6s+,J7s+,T7s+,A2o+,K8o+,Q9o+,J9o+",
        "BB":  "22+,A2s+,K3s+,Q5s+,J6s+,T6s+,A2o+,K7o+,Q8o+,J8o+",
    },

    "unknown": {
        "UTG": "66+,ATs+,KQs,AQo+",
        "MP":  "55+,ATs+,KJs+,QJs,AQo+,KQo",
        "CO":  "44+,A8s+,KTs+,QTs+,JTs,ATo+,KQo",
        "BTN": "22+,A2s+,K9s+,Q9s+,J9s+,T9s,98s,87s,A9o+,KTo+,QTo+,JTo",
        "SB":  "22+,A2s+,K8s+,Q9s+,J9s+,T8s+,A8o+,KTo+,QTo+,JTo",
        "BB":  "22+,A2s+,K7s+,Q8s+,J8s+,T8s+,A8o+,KTo+,QTo+,JTo",
    },
}
