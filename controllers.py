import time

try:
    from gpiozero import RotaryEncoder, Button
    from gpiozero.exc import BadPinFactory
except Exception:
    RotaryEncoder = None
    Button = None
    BadPinFactory = None


NAV_PREVIOUS = "previous"
NAV_NEXT = "next"
NAV_CLICK = "click"
NAV_MENU = "menu"

MENU_ROW_DOWN = "row_down"
MENU_ROW_UP = "row_up"
MENU_VALUE_DOWN = "value_down"
MENU_VALUE_UP = "value_up"
MENU_OK = "ok"
MENU_BACK = "back"


class KnobInputController:
    def __init__(
        self,
        clk_pin=17,
        dt_pin=18,
        sw_pin=27,
        menu_pin=23,
        invert_rotation=False,
    ):
        self.invert_rotation = invert_rotation

        self._pending_previous = 0
        self._pending_next = 0
        self._pending_click = 0
        self._pending_menu = 0

        self._encoder = None
        self._sw_button = None
        self._menu_button = None
        self._enabled = False

        self._last_steps = 0
        self._last_sw_pressed = False
        self._last_menu_pressed = False

        self._last_click_time = 0.0
        self._last_menu_time = 0.0
        self._click_debounce_sec = 0.20

        if (
            RotaryEncoder is not None
            and Button is not None
        ):
            try:
                self._encoder = RotaryEncoder(
                    a=clk_pin,
                    b=dt_pin,
                    wrap=True,
                )
                self._sw_button = Button(sw_pin)
                self._menu_button = Button(menu_pin)

                self._last_steps = self._encoder.steps
                self._last_sw_pressed = self._sw_button.is_pressed
                self._last_menu_pressed = self._menu_button.is_pressed

                self._enabled = True
            except Exception:
                self._encoder = None
                self._sw_button = None
                self._menu_button = None
                self._enabled = False

    @property
    def enabled(self):
        return self._enabled

    def close(self):
        for device in (self._encoder, self._sw_button, self._menu_button):
            if device is None:
                continue
            try:
                device.close()
            except Exception:
                pass
        self._encoder = None
        self._sw_button = None
        self._menu_button = None
        self._enabled = False

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def update(self):
        if not self._enabled:
            return

        current_steps = self._encoder.steps
        delta = current_steps - self._last_steps
        if delta != 0:
            is_next = delta > 0
            if self.invert_rotation:
                is_next = not is_next
            if is_next:
                self._pending_next += 1
            else:
                self._pending_previous += 1
        self._last_steps = current_steps

        sw_pressed = self._sw_button.is_pressed
        if sw_pressed and not self._last_sw_pressed:
            now = time.monotonic()
            if now - self._last_click_time >= self._click_debounce_sec:
                self._last_click_time = now
                self._pending_click += 1
        self._last_sw_pressed = sw_pressed

        menu_pressed = self._menu_button.is_pressed
        if menu_pressed and not self._last_menu_pressed:
            now = time.monotonic()
            if now - self._last_menu_time >= self._click_debounce_sec:
                self._last_menu_time = now
                self._pending_menu += 1
        self._last_menu_pressed = menu_pressed

    # ------------------------------------------------------------------
    # Command consumption
    # ------------------------------------------------------------------

    def _consume_one(self, bucket):
        if bucket <= 0:
            return False, 0
        return True, bucket - 1

    def previous(self):
        ok, new_val = self._consume_one(self._pending_previous)
        if ok:
            self._pending_previous = new_val
        return ok

    def next(self):
        ok, new_val = self._consume_one(self._pending_next)
        if ok:
            self._pending_next = new_val
        return ok

    def click(self):
        ok, new_val = self._consume_one(self._pending_click)
        if ok:
            self._pending_click = new_val
        return ok

    def menu(self):
        ok, new_val = self._consume_one(self._pending_menu)
        if ok:
            self._pending_menu = new_val
        return ok


class MenuKnobController:
    """
    Separate menu hardware: one rotary encoder (with built-in push button).
    No dedicated back button is required.

    Pin usage (different from the NAV controller):
    - Menu encoder (wheel + press):
        menu_clk_pin, menu_dt_pin  -> wheel rotation (rows or value edit)
        menu_sw_pin                -> press = OK / toggle edit

    Wheel behavior depends on the menu "edit mode" (managed by the menu
    controller, not here):
    - When NOT editing a value -> wheel moves rows up/down
    - When editing a value     -> wheel increases/decreases the value
    - Press (OK)               -> enter/exit edit mode or confirm action

    To exit the menu entirely, users navigate (wheel) to the "Exit menu"
    row and press OK.
    """

    def __init__(
        self,
        menu_clk_pin=26,
        menu_dt_pin=20,
        menu_sw_pin=21,
        invert_wheel_rotation=False,
    ):
        self.invert_wheel_rotation = invert_wheel_rotation

        self._pending_wheel_up = 0
        self._pending_wheel_down = 0
        self._pending_ok = 0

        self._menu_encoder = None
        self._sw_button = None
        self._enabled = False

        self._last_encoder_steps = 0
        self._last_sw_pressed = False

        self._last_sw_time = 0.0
        self._debounce_sec = 0.20

        if RotaryEncoder is not None and Button is not None:
            try:
                self._menu_encoder = RotaryEncoder(
                    a=menu_clk_pin,
                    b=menu_dt_pin,
                    wrap=True,
                )
                self._sw_button = Button(menu_sw_pin)

                self._last_encoder_steps = self._menu_encoder.steps
                self._last_sw_pressed = self._sw_button.is_pressed

                self._enabled = True
            except Exception:
                for dev in (self._menu_encoder, self._sw_button):
                    try:
                        if dev is not None:
                            dev.close()
                    except Exception:
                        pass
                self._menu_encoder = None
                self._sw_button = None
                self._enabled = False

    @property
    def enabled(self):
        return self._enabled

    def close(self):
        for dev in (self._menu_encoder, self._sw_button):
            if dev is None:
                continue
            try:
                dev.close()
            except Exception:
                pass
        self._menu_encoder = None
        self._sw_button = None
        self._enabled = False

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def update(self):
        if not self._enabled:
            return

        current_steps = self._menu_encoder.steps
        delta = current_steps - self._last_encoder_steps
        if delta != 0:
            is_up = delta > 0
            if self.invert_wheel_rotation:
                is_up = not is_up
            if is_up:
                self._pending_wheel_up += 1
            else:
                self._pending_wheel_down += 1
        self._last_encoder_steps = current_steps

        sw_pressed = self._sw_button.is_pressed
        if sw_pressed and not self._last_sw_pressed:
            now = time.monotonic()
            if now - self._last_sw_time >= self._debounce_sec:
                self._last_sw_time = now
                self._pending_ok += 1
        self._last_sw_pressed = sw_pressed

    # ------------------------------------------------------------------
    # Command consumption
    # ------------------------------------------------------------------

    def _consume(self, bucket):
        if bucket <= 0:
            return False, 0
        return True, bucket - 1

    def wheel_up(self):
        ok, new = self._consume(self._pending_wheel_up)
        if ok:
            self._pending_wheel_up = new
        return ok

    def wheel_down(self):
        ok, new = self._consume(self._pending_wheel_down)
        if ok:
            self._pending_wheel_down = new
        return ok

    def ok(self):
        ok, new = self._consume(self._pending_ok)
        if ok:
            self._pending_ok = new
        return ok
