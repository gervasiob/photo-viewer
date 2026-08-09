import os
import json
import random
import time


SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "settings.json",
)

ORDER_ASC = "asc"
ORDER_DESC = "desc"
ORDER_RANDOM = "random"

ALL_ORDERS = (ORDER_ASC, ORDER_DESC, ORDER_RANDOM)

DEFAULT_IMAGE_DISPLAY_MS = 5_000
DEFAULT_ORDER = ORDER_ASC

IMAGE_DISPLAY_OPTIONS_MS = (
    3_000,
    5_000,
    8_000,
    10_000,
    15_000,
    30_000,
    60_000,
)


class Settings:
    def __init__(self):
        self.image_display_ms = DEFAULT_IMAGE_DISPLAY_MS
        self.order = DEFAULT_ORDER

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path=SETTINGS_PATH):
        settings = cls()
        if not os.path.exists(path):
            settings.save(path=path)
            return settings

        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return settings

        try:
            value = int(data.get("image_display_ms", DEFAULT_IMAGE_DISPLAY_MS))
            if value <= 0:
                value = DEFAULT_IMAGE_DISPLAY_MS
        except Exception:
            value = DEFAULT_IMAGE_DISPLAY_MS
        settings.image_display_ms = value

        order = data.get("order", DEFAULT_ORDER)
        if order not in ALL_ORDERS:
            order = DEFAULT_ORDER
        settings.order = order

        return settings

    def save(self, path=SETTINGS_PATH):
        data = {
            "image_display_ms": int(self.image_display_ms),
            "order": str(self.order),
        }
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def apply_image_display_option_index(self, index):
        index = max(0, min(index, len(IMAGE_DISPLAY_OPTIONS_MS) - 1))
        self.image_display_ms = IMAGE_DISPLAY_OPTIONS_MS[index]

    def image_display_option_index(self):
        try:
            return IMAGE_DISPLAY_OPTIONS_MS.index(self.image_display_ms)
        except ValueError:
            nearest = min(
                range(len(IMAGE_DISPLAY_OPTIONS_MS)),
                key=lambda i: abs(IMAGE_DISPLAY_OPTIONS_MS[i] - self.image_display_ms),
            )
            self.image_display_ms = IMAGE_DISPLAY_OPTIONS_MS[nearest]
            return nearest

    def order_index(self):
        try:
            return ALL_ORDERS.index(self.order)
        except ValueError:
            return 0

    def apply_order_index(self, index):
        index = max(0, min(index, len(ALL_ORDERS) - 1))
        self.order = ALL_ORDERS[index]


def order_files(file_paths, order_mode):
    files = list(file_paths)
    if order_mode == ORDER_DESC:
        return sorted(files, reverse=True)
    if order_mode == ORDER_RANDOM:
        shuffled = list(files)
        random.shuffle(shuffled)
        return shuffled
    return sorted(files)
