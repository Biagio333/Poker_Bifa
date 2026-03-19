import cv2
import numpy as np
import os


class image_search:
    def __init__(self, roi_map, name_table="default",scale_factor=0.8):
      
        self.roi_map = roi_map
        self.card_table_img = None
        self.card_hero_img = None
        self.covered_card_img = None
        self.dealer_button_img = None
        self.scale_factor = scale_factor
    
    def load_images(self, path_images):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Carica immagini da cards_board
        cards_board_path = os.path.join(base_path, "data", path_images, "cards_board")
        cards_board_images = []
        for card_file in os.listdir(cards_board_path):
            if card_file.endswith(('.jpg', '.png', '.jpeg')):
                card_path = os.path.join(cards_board_path, card_file)
                img = cv2.imread(card_path)
                if img is not None and img.size > 0:
                    img = cv2.resize(img, None, fx=self.scale_factor, fy=self.scale_factor)  # Ingrandisci di scale_factor
                    card_name = os.path.splitext(card_file)[0]  # Rimuovi estensione
                    cards_board_images.append([img, card_name])
                else:
                    print(f"Immagine corrotta saltata: {card_file}")
        self.card_table_img = cards_board_images
        
        # Carica immagini da cards_hero (usa le stesse di board ma ingrandite)
        cards_hero_images = []
        for img, name in cards_board_images:
            # Ingrandisci le immagini per hero
            hero_img = cv2.resize(img, None, fx=1.2, fy=1.2)
            cards_hero_images.append([hero_img, name])
        self.card_hero_img = cards_hero_images
        
        # Carica immagini da covered_card
        covered_card_path = os.path.join(base_path, "data", path_images, "covered_card")
        covered_card_images = []
        for card_file in os.listdir(covered_card_path):
            if card_file.endswith(('.jpg', '.png', '.jpeg')):
                card_path = os.path.join(covered_card_path, card_file)
                img = cv2.imread(card_path)
                if img is not None:
                    # Ridimensiona anche le carte coperte come le altre immagini
                    img = cv2.resize(img, None, fx=1, fy=1)
                    card_name = os.path.splitext(card_file)[0]  # Rimuovi estensione
                    covered_card_images.append([img, card_name])
                    print(f"Caricata carta coperta: {card_name}")
        self.covered_card_img = covered_card_images
        
        # Carica immagini da dealer_button
        dealer_button_path = os.path.join(base_path, "data", path_images, "dealer_button")
        dealer_button_images = []
        for card_file in os.listdir(dealer_button_path):
            if card_file.endswith(('.jpg', '.png', '.jpeg')):
                card_path = os.path.join(dealer_button_path, card_file)
                img = cv2.imread(card_path)
                if img is not None and img.size > 0:
                    img = cv2.resize(img, None, fx=self.scale_factor, fy=self.scale_factor)  # Scala a 0.4 come le altre immagini
                    card_name = os.path.splitext(card_file)[0]  # Rimuovi estensione
                    dealer_button_images.append([img, card_name])
                else:
                    print(f"Immagine dealer corrotta saltata: {card_file}")
        self.dealer_button_img = dealer_button_images
        
        print(f"Caricate {len(cards_board_images)} immagini board, {len(cards_hero_images)} hero (da board ingrandite), {len(covered_card_images)} covered, {len(dealer_button_images)} dealer")
        return cards_board_images, cards_hero_images, covered_card_images, dealer_button_images

    def find_table_cards(self, table_img, threshold=0.88):
        """
        Cerca le carte nel ROI 'carte_tavolo' usando template matching con NMS.
        
        Args:
            table_img: Immagine del tavolo (screenshot)
            threshold: Soglia di matching (0-1, default 0.9)
            
        Returns:
            Lista dei nomi delle carte trovate
        """
        # Ottieni il ROI delle carte del tavolo
        roi_data = self.roi_map.get("carte_tavolo")
        if not roi_data:
            print("ROI 'carte_tavolo' non trovato")
            return []
        
        # Estrai la regione di interesse
        x, y, w, h = roi_data["x"], roi_data["y"], roi_data["w"], roi_data["h"]
        table_roi = table_img[y:y+h, x:x+w]
        
        found_cards = []
        used_positions = []  # Lista di (x, y, w, h) delle posizioni già usate
        
        # Confronta con ogni template delle carte del board
        for template, name in self.card_table_img:
            result = cv2.matchTemplate(table_roi, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                # Controlla se questa posizione si sovrappone con posizioni già usate
                template_h, template_w = template.shape[:2]
                match_x, match_y = max_loc
                match_rect = (match_x, match_y, template_w, template_h)
                
                overlap = False
                for used_x, used_y, used_w, used_h in used_positions:
                    # Calcola overlap (semplificato: se i rettangoli si intersecano)
                    if (match_x < used_x + used_w and match_x + template_w > used_x and
                        match_y < used_y + used_h and match_y + template_h > used_y):
                        overlap = True
                        break
                
                if not overlap:
                    found_cards.append(name)
                    used_positions.append(match_rect)
                    #print(f"Trovata carta: {name} con confidenza {max_val:.3f} at ({match_x}, {match_y})")
        
        return found_cards

    def find_hero_cards(self, table_img, threshold=0.9):
        """
        Cerca le carte hero nel ROI 'carte_hero' usando template matching con NMS.
        
        Args:
            table_img: Immagine del tavolo (screenshot)
            threshold: Soglia di matching (0-1, default 0.9)
            
        Returns:
            Lista dei nomi delle carte hero trovate
        """
        # Ottieni il ROI delle carte hero
        roi_data = self.roi_map.get("carte_hero")
        if not roi_data:
            print("ROI 'carte_hero' non trovato - devi aggiungerlo nel JSON con Labelme")
            return []
        
        # Estrai la regione di interesse
        x, y, w, h = roi_data["x"], roi_data["y"], roi_data["w"], roi_data["h"]
        table_roi = table_img[y:y+h, x:x+w]
        
        found_cards = []
        used_positions = []  # Lista di (x, y, w, h) delle posizioni già usate
        
        # Confronta con ogni template delle carte hero
        for template, name in self.card_hero_img:
            result = cv2.matchTemplate(table_roi, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                # Controlla se questa posizione si sovrappone con posizioni già usate
                template_h, template_w = template.shape[:2]
                match_x, match_y = max_loc
                match_rect = (match_x, match_y, template_w, template_h)
                
                overlap = False
                for used_x, used_y, used_w, used_h in used_positions:
                    # Calcola overlap (semplificato: se i rettangoli si intersecano)
                    if (match_x < used_x + used_w and match_x + template_w > used_x and
                        match_y < used_y + used_h and match_y + template_h > used_y):
                        overlap = True
                        break
                
                if not overlap:
                    found_cards.append(name)
                    used_positions.append(match_rect)
                    #print(f"Trovata carta hero: {name} con confidenza {max_val:.3f} at ({match_x}, {match_y})")
        
        return found_cards

    def find_dealer_button(self, table_img, threshold=0.8):
        """
        Cerca il dealer button e determina quale player lo ha basandosi sulla vicinanza.
        
        Args:
            table_img: Immagine del tavolo (screenshot)
            threshold: Soglia di matching (0-1, default 0.8)
            
        Returns:
            Numero del seat del dealer (0-5) o None
        """
        # Ottieni il ROI del dealer button
        roi_data = self.roi_map.get("dealer_button")
        if not roi_data:
            print("ROI 'dealer_button' non trovato - devi aggiungerlo nel JSON con Labelme")
            return None
        
        # Estrai la regione di interesse
        x, y, w, h = roi_data["x"], roi_data["y"], roi_data["w"], roi_data["h"]
        table_roi = table_img[y:y+h, x:x+w]
        
        # Confronta con ogni template del dealer button
        best_match = None
        best_confidence = 0
        best_location = None
        
        for template, name in self.dealer_button_img:
            result = cv2.matchTemplate(table_roi, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold and max_val > best_confidence:
                best_confidence = max_val
                best_match = name
                best_location = (max_loc[0] + x, max_loc[1] + y)  # Posizione assoluta
        
        if best_location:
            #print(f"Trovato dealer button con confidenza {best_confidence:.3f} at ({best_location[0]}, {best_location[1]})")
            
            # Trova il player più vicino
            dealer_seat = self._find_nearest_player(best_location)
            #print(f"Dealer è il player: {dealer_seat}")
            return dealer_seat
        
        return None

    def _find_nearest_player(self, dealer_pos):
        """
        Trova il player più vicino alla posizione del dealer button.
        
        Args:
            dealer_pos: Tupla (x, y) della posizione del dealer button
            
        Returns:
            Numero del seat del player più vicino (0-5)
        """
        min_distance = float('inf')
        nearest_player = None
        
        for i in range(6):
            player_roi = self.roi_map.get(f"player_{i}_name")
            if player_roi:
                # Calcola il centro del ROI del player
                player_center_x = player_roi["x"] + player_roi["w"] / 2
                player_center_y = player_roi["y"] + player_roi["h"] / 2
                
                # Calcola distanza euclidea
                distance = ((dealer_pos[0] - player_center_x) ** 2 + (dealer_pos[1] - player_center_y) ** 2) ** 0.5
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_player = i
        
        return nearest_player

    def find_covered_cards(self, table_img, threshold=0.6):
        """
        Cerca carte coperte in un rettangolo che copre tutte le posizioni dei giocatori.
        
        Args:
            table_img: Immagine del tavolo (screenshot)
            threshold: Soglia di matching (0-1, default 0.6 - più bassa per carte coperte)
            
        Returns:
            Lista dei seat che hanno carte coperte (sono ancora in mano)
        """
        # Usa un ROI grande che copre tutte le posizioni dei giocatori
        roi_data = self.roi_map.get("covered_cards_area")
        if not roi_data:
            print("ROI 'covered_cards_area' non trovato - usa logica di fallback")
            # Fallback: usa l'intera immagine se non c'è ROI specifico
            h, w = table_img.shape[:2]
            roi_data = {"x": 0, "y": 0, "w": w, "h": h}
        
        # Estrai la regione di interesse grande
        x, y, w, h = roi_data["x"], roi_data["y"], roi_data["w"], roi_data["h"]
        search_roi = table_img[y:y+h, x:x+w]
        
        # Trova tutte le carte coperte in questa area
        found_positions = []
        all_confidences = []  # Per debug: tutti i valori di confidenza
        
        for template, name in self.covered_card_img:
            result = cv2.matchTemplate(search_roi, template, cv2.TM_CCOEFF_NORMED)
            
            # Trova il valore massimo per questo template
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            all_confidences.append(max_val)
            
            # Trova tutti i match sopra la soglia
            locations = np.where(result >= threshold)
            for pt in zip(*locations[::-1]):
                found_positions.append((pt[0] + x, pt[1] + y))  # Posizione assoluta
        
        # Debug: mostra i valori di confidenza
        if all_confidences:
            max_conf = max(all_confidences)
            avg_conf = sum(all_confidences) / len(all_confidences)
            #print(f"Carte coperte - Max confidence: {max_conf:.3f}, Avg: {avg_conf:.3f}, Threshold: {threshold}")
        
        #print(f"Trovate {len(found_positions)} carte coperte (threshold: {threshold})")
        
        # Associa ogni carta coperta trovata al giocatore più vicino
        active_seats = set()
        for card_pos in found_positions:
            nearest_seat = self._find_nearest_player(card_pos)
            if nearest_seat is not None:
                active_seats.add(nearest_seat)
        
        return list(active_seats)

    def test_covered_cards_threshold(self, table_img, test_thresholds=[0.55, 0.6, 0.65]):
        """
        Testa diversi valori di soglia per le carte coperte e mostra i risultati.
        
        Args:
            table_img: Immagine del tavolo (screenshot)
            test_thresholds: Lista di soglie da testare
            
        Returns:
            None (stampa i risultati)
        """
        print("\n=== TEST SOGLIE CARTE COPERTE ===")
        
        # Usa un ROI grande che copre tutte le posizioni dei giocatori
        roi_data = self.roi_map.get("covered_cards_area")
        if not roi_data:
            h, w = table_img.shape[:2]
            roi_data = {"x": 0, "y": 0, "w": w, "h": h}
        
        x, y, w, h = roi_data["x"], roi_data["y"], roi_data["w"], roi_data["h"]
        search_roi = table_img[y:y+h, x:x+w]
        
        for threshold in test_thresholds:
            found_positions = []
            max_conf = 0
            
            for template, name in self.covered_card_img:
                result = cv2.matchTemplate(search_roi, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                max_conf = max(max_conf, max_val)
                
                locations = np.where(result >= threshold)
                for pt in zip(*locations[::-1]):
                    found_positions.append((pt[0] + x, pt[1] + y))
            
            # Conta giocatori attivi
            active_seats = set()
            for card_pos in found_positions:
                nearest_seat = self._find_nearest_player(card_pos)
                if nearest_seat is not None:
                    active_seats.add(nearest_seat)
            
            print(f"Soglia {threshold:.1f}: {len(found_positions)} carte, {len(active_seats)} giocatori attivi, max_conf={max_conf:.3f}")
        
        print("=== FINE TEST ===\n")

    def get_player_positions(self, dealer_seat):
        """
        Determina le posizioni dei giocatori basate sul seat del dealer.
        
        Args:
            dealer_seat: Numero del seat del dealer (0-5)
            
        Returns:
            Dict con posizioni: {"UTG": seat, "MP": seat, "CO": seat, "BTN": seat, "SB": seat, "BB": seat}
        """
        if dealer_seat is None:
            return {}
        
        # Posizioni relative al dealer (6 giocatori)
        positions = {}
        positions["BTN"] = dealer_seat  # Button = dealer
        
        # Calcola le altre posizioni in senso orario
        positions["SB"] = (dealer_seat + 1) % 6
        positions["BB"] = (dealer_seat + 2) % 6
        positions["UTG"] = (dealer_seat + 3) % 6
        positions["MP"] = (dealer_seat + 4) % 6  # Middle position
        positions["CO"] = (dealer_seat + 5) % 6  # Cutoff
        
        return positions