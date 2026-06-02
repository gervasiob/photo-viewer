import pygame

import time

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None


class KeyboardController:

    def __init__(self):
        self._previous = False
        self._next = False
        self._click = False

    def handle_event(self, event):

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_LEFT:
            self._previous = True

        elif event.key == pygame.K_RIGHT:
            self._next = True

        elif event.key == pygame.K_RETURN:
            self._click = True

    def previous(self):
        value = self._previous
        self._previous = False
        return value

    def next(self):
        value = self._next
        self._next = False
        return value

    def click(self):
        value = self._click
        self._click = False
        return value


class PhotoFrameController:

    def __init__(
        self,
        enable_gpio=True,
        clk_pin=17,
        dt_pin=18,
        sw_pin=27,
        invert_rotation=False,
    ):
        self._keyboard = KeyboardController()

        self._pending_previous = 0
        self._pending_next = 0
        self._pending_click = 0

        self._gpio_enabled = False
        self._invert_rotation = invert_rotation
        self._clk_pin = clk_pin
        self._dt_pin = dt_pin
        self._sw_pin = sw_pin

        self._last_clk_state = 1
        self._last_sw_state = 1
        self._last_rotate_time = 0.0
        self._rotate_debounce_sec = 0.001
        self._last_click_time = 0.0
        self._click_debounce_sec = 0.15

        if enable_gpio:
            self._setup_gpio()

    def _setup_gpio(self):
        if GPIO is None:
            return

        GPIO.setmode(GPIO.BCM)

        GPIO.setup(
            self._clk_pin,
            GPIO.IN,
            pull_up_down=GPIO.PUD_UP
        )

        GPIO.setup(
            self._dt_pin,
            GPIO.IN,
            pull_up_down=GPIO.PUD_UP
        )

        GPIO.setup(
            self._sw_pin,
            GPIO.IN,
            pull_up_down=GPIO.PUD_UP
        )

        self._last_clk_state = GPIO.input(self._clk_pin)
        self._last_sw_state = GPIO.input(self._sw_pin)

        self._gpio_enabled = True

    def close(self):
        if GPIO is None or not self._gpio_enabled:
            return

        try:
            GPIO.cleanup(
                (self._clk_pin, self._dt_pin, self._sw_pin)
            )
        except Exception:
            pass

        self._gpio_enabled = False

    def update(self):
        if GPIO is None or not self._gpio_enabled:
            return

        clk_state = GPIO.input(self._clk_pin)

        if clk_state != self._last_clk_state:
            self._last_clk_state = clk_state

            if clk_state == 0:
                now = time.monotonic()

                if now - self._last_rotate_time >= self._rotate_debounce_sec:
                    self._last_rotate_time = now

                    dt_state = GPIO.input(self._dt_pin)
                    is_next = (dt_state != clk_state)

                    if self._invert_rotation:
                        is_next = not is_next

                    if is_next:
                        self._pending_next += 1
                    else:
                        self._pending_previous += 1

        sw_state = GPIO.input(self._sw_pin)

        if sw_state != self._last_sw_state:
            self._last_sw_state = sw_state

            if sw_state == 0:
                now = time.monotonic()

                if now - self._last_click_time >= self._click_debounce_sec:
                    self._last_click_time = now
                    self._pending_click += 1

    def handle_event(self, event):
        self._keyboard.handle_event(event)

    def previous(self):
        if self._keyboard.previous():
            return True

        if self._pending_previous > 0:
            self._pending_previous -= 1
            return True

        return False

    def next(self):
        if self._keyboard.next():
            return True

        if self._pending_next > 0:
            self._pending_next -= 1
            return True

        return False

    def click(self):
        if self._keyboard.click():
            return True

        if self._pending_click > 0:
            self._pending_click -= 1
            return True

        return False
