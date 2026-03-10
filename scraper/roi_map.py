import json


class ROIMap:
    """
    Gestisce le ROI del tavolo.
    Supporta:
    - JSON già convertito: {"nome": {"x":..,"y":..,"w":..,"h":..}}
    - JSON originale di Labelme con "shapes"
    """

    def __init__(self, json_path: str):
        self.json_path = json_path
        self.data = {}

    def load(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Caso 1: file già convertito
        if "shapes" not in raw:
            self.data = raw
            return

        # Caso 2: file Labelme
        converted = {}

        for shape in raw.get("shapes", []):
            label = shape.get("label")
            points = shape.get("points", [])

            if not label or len(points) < 2:
                continue

            x1, y1 = points[0]
            x2, y2 = points[1]

            x = int(min(x1, x2))
            y = int(min(y1, y2))
            w = int(abs(x2 - x1))
            h = int(abs(y2 - y1))

            converted[label] = {
                "x": x,
                "y": y,
                "w": w,
                "h": h
            }

        self.data = converted

    def get(self, name: str):
        return self.data.get(name)

    def all(self):
        return self.data