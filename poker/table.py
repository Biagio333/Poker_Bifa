import shutil
import textwrap

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
    - pulsanti azione disponibili
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

        self.available_actions = []
        self.buttons_visible = False
        self._prev_board_len = 0

    def get_player(self, seat: int):
        return self.players[seat]

    def set_pot(self, pot: float):
        self.pot = pot

    def set_board_cards(self, cards):
        new_cards = list(cards or [])
        self.board_cards = new_cards
        
        street_new = self._street_from_board()
        for p in self.players:
            p.current_street_old_frame = self.street
            p.current_street = street_new
        self.street = street_new
        # Nuova mano: il board era popolato e ora è vuoto → reset azioni per street
        if self._prev_board_len > 0 and len(new_cards) == 0:
            for p in self.players:
                for street in p.actions_by_street:
                    p.actions_by_street[street].clear()
                p.actions.clear()
        

        self._prev_board_len = len(new_cards)



    def set_hero_cards(self, cards):
        self.hero_cards = list(cards or [])

    def reset_hand_state(self):
        self.pot = 0.0
        self.board_cards.clear()
        self.hero_cards.clear()
        self.street = "preflop"

        self.available_actions.clear()
        self.buttons_visible = False

        for p in self.players:
            p.current_street = self.street

    def set_available_actions(self, actions):
        self.available_actions = list(actions or [])
        self.buttons_visible = len(self.available_actions) > 0

    def format_available_actions(self, scale=1.0):
        if not self.available_actions:
            return "Azioni disponibili: []"

        lines = ["Azioni disponibili:"]
        for action in self.available_actions:
            label = action.get("label", "")
            click_point = action.get("click_point", {})
            x = click_point.get("x", "?")
            y = click_point.get("y", "?")

            if (
                isinstance(x, (int, float))
                and isinstance(y, (int, float))
                and isinstance(scale, (int, float))
                and scale not in (0, 0.0)
            ):
                x = int(round(x / scale))
                y = int(round(y / scale))

            lines.append(f"{label} -> ({x}, {y})")

        return "\n".join(lines)

    def format_players_stats(self, seat_to_position=None):
        streets = ("preflop", "flop", "turn", "river")
        term_width = shutil.get_terminal_size(fallback=(160, 40)).columns-55
        seat_to_position = seat_to_position or {}

        stat_columns = [
            ("Seat", 4, ">"),
            ("Pos", 4, "<"),
            ("Name", 14, "<"),
            ("Hands", 5, ">"),
            ("VPIP", 6, ">"),
            ("PFR", 6, ">"),
            ("Call", 6, ">"),
            ("Bet", 6, ">"),
            ("Raise", 6, ">"),
            ("Fold", 6, ">"),
            ("Invested", 8, ">"),
        ]

        fixed_width = sum(width for _, width, _ in stat_columns)
        fixed_width += 3 * (len(stat_columns) - 1)
        remaining_width = max(term_width - fixed_width - 3, 64)
        street_col_w = max(16, remaining_width // len(streets))

        def fmt_acts(acts):
            if not acts:
                return "-"
            return ", ".join(
                f"{a['action']}({a['amount']:.2f})" if a['amount'] else a['action']
                for a in acts
            )

        def align(text, width, direction):
            if direction == ">":
                return f"{text:>{width}}"
            return f"{text:<{width}}"

        def truncate(text, width):
            if len(text) <= width:
                return text
            if width <= 3:
                return text[:width]
            return text[: width - 3] + "..."

        columns = stat_columns + [
            (street.upper(), street_col_w, "<") for street in streets
        ]

        header = " | ".join(
            align(label, width, direction)
            for label, width, direction in columns
        )
        sep = "-+-".join("-" * width for _, width, _ in columns)
        lines = [sep, header, sep]

        for p in self.players:
            base_cells = [
                str(p.seat),
                seat_to_position.get(p.seat, "-"),
                truncate(p.name or "???", 14),
                str(p.get_total_hands()),
                f"{p.get_stat_percentage('vpip'):.1f}%",
                f"{p.get_stat_percentage('pfr'):.1f}%",
                f"{p.get_stat_percentage('call'):.1f}%",
                f"{p.get_stat_percentage('bet'):.1f}%",
                f"{p.get_stat_percentage('raise'):.1f}%",
                f"{p.get_stat_percentage('fold'):.1f}%",
                f"{p.total_invested:.2f}",
            ]
            street_cells = [fmt_acts(p.actions_by_street.get(st, [])) for st in streets]
            row_cells = base_cells + street_cells

            wrapped_cells = []
            for (label, width, _direction), cell in zip(columns, row_cells):
                if label in {"Seat", "Hands", "VPIP", "PFR", "Call", "Bet", "Raise", "Fold", "Invested"}:
                    wrapped_cells.append([cell])
                    continue
                wrapped = textwrap.wrap(
                    cell,
                    width=width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                wrapped_cells.append(wrapped or [""])

            row_height = max(len(cell_lines) for cell_lines in wrapped_cells)
            for row_index in range(row_height):
                rendered = []
                for (label, width, direction), cell_lines in zip(columns, wrapped_cells):
                    value = cell_lines[row_index] if row_index < len(cell_lines) else ""
                    if row_index > 0 and label in {"Seat", "Hands", "VPIP", "PFR", "Call", "Bet", "Raise", "Fold", "Invested"}:
                        value = ""
                    rendered.append(align(value, width, direction))
                lines.append(" | ".join(rendered))
            lines.append(sep)

        return "\n".join(lines)

    def _street_from_board(self):
        board_len = len(self.board_cards)

        if board_len >= 5:
            return "river"
        if board_len == 4:
            return "turn"
        if board_len == 3:
            return "flop"
        if board_len == 0:
            return "preflop"
        return "preflop"
