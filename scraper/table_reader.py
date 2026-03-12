from scraper.ocr_utils import ocr_in_roi, ocr_results_to_text, parse_amount


class TableReader:
    """
    Legge le informazioni del tavolo partendo da:
    - ROI del tavolo
    - risultati OCR full-screen

    Popola:
    - nome player
    - stack player
    - pot
    """

    def __init__(self, roi_map, min_score=0.5):
        self.roi_map = roi_map
        self.min_score = min_score

    

    def read_text_from_roi(self, ocr_results, roi_name: str) -> str:
        roi = self.roi_map.get(roi_name)
        items = ocr_in_roi(ocr_results, roi, self.min_score)
        return ocr_results_to_text(items)

    def read_amount_from_roi(self, ocr_results, roi_name: str) -> float:
        text = self.read_text_from_roi(ocr_results, roi_name)
        
        return parse_amount(text)

    def populate_player(self, player, ocr_results):
        """
        Popola name, stack e puntata corrente di un singolo player.
        Cerca:
        - player_{seat}_name
        - player_{seat}_stack
        - player_{seat}_bet
        """
        seat = player.seat

        name_roi_name = f"player_{seat}_name"
        stack_roi_name = f"player_{seat}_stack"
        bet_roi_name = f"player_{seat}_bet"

        name_text = self.read_text_from_roi(ocr_results, name_roi_name)
        if name_text:
            player.set_name(name_text)

        stack_value = self.read_amount_from_roi(ocr_results, stack_roi_name)
        if stack_value > 0:
            player.update_stack(stack_value)

        bet_value = self.read_amount_from_roi(ocr_results, bet_roi_name)
        player.update_current_bet(bet_value if bet_value > 0 else 0.0)

    def populate_all_players(self, table, ocr_results):
        """
        Popola tutti i player del tavolo.
        """
        for player in table.players:
            self.populate_player(player, ocr_results)

    def read_pot(self, ocr_results) -> float:
        """
        Legge il pot dalla ROI 'pot'.
        """
        return self.read_amount_from_roi(ocr_results, "pot")

    def populate_table(self, table, ocr_results):
        """
        Popola tutto il tavolo:
        - players
        - pot
        """
        self.populate_all_players(table, ocr_results)

        pot_value = self.read_pot(ocr_results)
        if pot_value > 0:
            table.set_pot(pot_value)

    def table_reset(self, table):

        # reset dati
        for p in table.players:
            #p.name = None
            p.stack = 0.0
            p.current_bet = 0.0

        table.reset_hand_state()
