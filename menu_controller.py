import pygame

from settings_model import (
    Settings,
    IMAGE_DISPLAY_OPTIONS_MS,
    ALL_ORDERS,
)


MENU_ITEM_DURATION = 0
MENU_ITEM_ORDER = 1
MENU_ITEM_SAVE = 2
MENU_ITEM_CANCEL = 3

MENU_ITEMS = (
    "Image time",
    "Order",
    "Save & exit",
    "Cancel",
)

ORDER_LABELS = {
    ALL_ORDERS[0]: "Ascending",
    ALL_ORDERS[1]: "Descending",
    ALL_ORDERS[2]: "Random",
}


def _duration_label(ms):
    seconds = ms / 1000.0
    if seconds.is_integer():
        return f"{int(seconds)}s"
    return f"{seconds:.1f}s"


class MenuController:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.settings = Settings.load()
        self._draft = Settings()
        self._sync_draft_from_settings()

        self._selected_row = MENU_ITEM_DURATION
        self._editing_value = False

        self._open = False

        try:
            self._title_font = pygame.font.SysFont(
                "arialhelveticadejavusansmono", 48, bold=True
            )
        except Exception:
            self._title_font = pygame.font.Font(None, 48)

        try:
            self._row_font = pygame.font.SysFont(
                "arialhelveticadejavusansmono", 36
            )
        except Exception:
            self._row_font = pygame.font.Font(None, 36)

        try:
            self._hint_font = pygame.font.SysFont(
                "arialhelveticadejavusansmono", 24
            )
        except Exception:
            self._hint_font = pygame.font.Font(None, 24)

    # ------------------------------------------------------------------
    # Settings bridge
    # ------------------------------------------------------------------

    def _sync_draft_from_settings(self):
        self._draft.image_display_ms = self.settings.image_display_ms
        self._draft.order = self.settings.order

    def effective_settings(self):
        return self.settings

    # ------------------------------------------------------------------
    # Open / close
    # ------------------------------------------------------------------

    @property
    def open(self):
        return self._open

    def open_menu(self):
        self._sync_draft_from_settings()
        self._selected_row = MENU_ITEM_DURATION
        self._editing_value = False
        self._open = True

    def close_menu(self, save=False):
        if save:
            self.settings.image_display_ms = self._draft.image_display_ms
            self.settings.order = self._draft.order
            self.settings.save()
            changed = True
        else:
            changed = False
        self._open = False
        self._editing_value = False
        return changed

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def move_row(self, delta):
        self._selected_row = max(
            0,
            min(len(MENU_ITEMS) - 1, self._selected_row + delta),
        )

    def change_value(self, delta):
        if self._selected_row == MENU_ITEM_DURATION:
            index = self._draft.image_display_option_index()
            index += delta
            index = max(0, min(len(IMAGE_DISPLAY_OPTIONS_MS) - 1, index))
            self._draft.apply_image_display_option_index(index)
        elif self._selected_row == MENU_ITEM_ORDER:
            index = self._draft.order_index()
            index += delta
            index = max(0, min(len(ALL_ORDERS) - 1, index))
            self._draft.apply_order_index(index)

    def activate_selected(self):
        if self._selected_row == MENU_ITEM_SAVE:
            return self.close_menu(save=True)
        if self._selected_row == MENU_ITEM_CANCEL:
            return self.close_menu(save=False)
        return None

    # ------------------------------------------------------------------
    # Knob-style commands (single wheel + press = OK, plus BACK)
    # ------------------------------------------------------------------

    @property
    def editing_value(self):
        return self._editing_value

    @property
    def selected_row_is_value(self):
        return self._selected_row in (MENU_ITEM_DURATION, MENU_ITEM_ORDER)

    def handle_wheel_up(self):
        if self._editing_value and self.selected_row_is_value:
            self.change_value(+1)
        else:
            self.move_row(-1)

    def handle_wheel_down(self):
        if self._editing_value and self.selected_row_is_value:
            self.change_value(-1)
        else:
            self.move_row(+1)

    def handle_ok(self):
        if self.selected_row_is_value:
            if not self._editing_value:
                self._editing_value = True
            else:
                self._editing_value = False
                if self._selected_row < len(MENU_ITEMS) - 1:
                    self.move_row(+1)
        else:
            self.activate_selected()

    def handle_back(self):
        if self._editing_value:
            self._editing_value = False
        else:
            self.close_menu(save=False)

    # ------------------------------------------------------------------
    # Legacy / deprecated helpers (kept so old code paths still compile)
    # ------------------------------------------------------------------

    def handle_row_up(self):
        if self._editing_value and self.selected_row_is_value:
            return
        self.move_row(-1)

    def handle_row_down(self):
        if self._editing_value and self.selected_row_is_value:
            return
        self.move_row(+1)

    def handle_value_down(self):
        if not self._editing_value:
            return
        self.change_value(-1)

    def handle_value_up(self):
        if not self._editing_value:
            return
        self.change_value(+1)

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.handle_back()
            return
        if event.key == pygame.K_UP:
            self.handle_wheel_up()
            return
        if event.key == pygame.K_DOWN:
            self.handle_wheel_down()
            return
        if event.key == pygame.K_LEFT:
            if self.editing_value and self.selected_row_is_value:
                self.change_value(-1)
            else:
                self.handle_back()
            return
        if event.key == pygame.K_RIGHT:
            if self.editing_value and self.selected_row_is_value:
                self.change_value(+1)
            else:
                self.handle_ok()
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.handle_ok()
            return

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _draw_row_value(self, screen, row, y, selected):
        if row == MENU_ITEM_DURATION:
            label = _duration_label(self._draft.image_display_ms)
            options = ", ".join(_duration_label(x) for x in IMAGE_DISPLAY_OPTIONS_MS)
            if self.editing_value and selected:
                value_text = f"EDIT {label}    [{options}]"
            else:
                value_text = f"{label}    [{options}]"
        elif row == MENU_ITEM_ORDER:
            label = ORDER_LABELS.get(self._draft.order, self._draft.order)
            options = ", ".join(ORDER_LABELS.get(o, o) for o in ALL_ORDERS)
            if self.editing_value and selected:
                value_text = f"EDIT {label}    [{options}]"
            else:
                value_text = f"{label}    [{options}]"
        elif row == MENU_ITEM_SAVE:
            value_text = "Confirm and save settings"
        elif row == MENU_ITEM_CANCEL:
            value_text = "Discard changes and go back"
        else:
            value_text = ""

        color = (255, 255, 120) if selected else (220, 220, 220)
        if self.editing_value and selected and self.selected_row_is_value:
            color = (120, 255, 160)
        rendered = self._row_font.render(value_text, True, color)
        screen.blit(rendered, (self.screen_width // 2 + 40, y + 4))

    def draw(self, screen):
        overlay = pygame.Surface(
            (self.screen_width, self.screen_height),
            pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 210))
        screen.blit(overlay, (0, 0))

        title = self._title_font.render(
            "Settings (wheel + OK button, or keyboard)",
            True,
            (255, 255, 255),
        )
        screen.blit(
            title,
            (
                (self.screen_width - title.get_width()) // 2,
                80,
            ),
        )

        start_y = 200
        row_h = 110
        for idx, label in enumerate(MENU_ITEMS):
            y = start_y + idx * row_h
            selected = (idx == self._selected_row)
            if selected:
                rect = pygame.Rect(
                    120,
                    y - 12,
                    self.screen_width - 240,
                    row_h - 20,
                )
                pygame.draw.rect(screen, (50, 80, 140), rect, border_radius=16)
                pygame.draw.rect(screen, (120, 180, 255), rect, width=3, border_radius=16)

            color = (255, 255, 255) if selected else (200, 200, 200)
            row_text = self._row_font.render(label, True, color)
            screen.blit(row_text, (160, y))

            self._draw_row_value(screen, idx, y, selected)

        hint = self._hint_font.render(
            "Wheel = move rows / edit value.  Press wheel = OK / toggle edit.  "
            "Back button or Esc = cancel.",
            True,
            (180, 180, 180),
        )
        screen.blit(
            hint,
            ((self.screen_width - hint.get_width()) // 2, self.screen_height - 80),
        )
