import pygame

import time

try:
    from gpiozero import RotaryEncoder, Button
except Exception:
    RotaryEncoder = None
    Button = None


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
        self._encoder = None

        if enable_gpio and RotaryEncoder is not None and Button is not None:
            self._encoder = EncoderController(
                clk_pin=clk_pin,
                dt_pin=dt_pin,
                sw_pin=sw_pin,
                invert_rotation=invert_rotation,
            )

    def close(self):
        if self._encoder is None:
            return

        try:
            self._encoder.close()
        except Exception:
            pass

    def update(self):
        if self._encoder is None:
            return
        self._encoder.poll()

    def handle_event(self, event):
        self._keyboard.handle_event(event)

    def previous(self):
        if self._keyboard.previous():
            return True
        return (
            self._encoder is not None
            and self._encoder.previous()
        )

    def next(self):
        if self._keyboard.next():
            return True
        return (
            self._encoder is not None
            and self._encoder.next()
        )

    def click(self):
        if self._keyboard.click():
            return True
        return (
            self._encoder is not None
            and self._encoder.click()
        )


class EncoderController:

    def __init__(
        self,
        clk_pin=17,
        dt_pin=18,
        sw_pin=27,
        invert_rotation=False,
    ):
        self.encoder = RotaryEncoder(
            a=clk_pin,
            b=dt_pin,
            wrap=True
        )

        self.button = Button(sw_pin)

        self._invert_rotation = invert_rotation
        self._previous = False
        self._next = False
        self._click = False

        self._last_steps = self.encoder.steps
        self._last_button_pressed = self.button.is_pressed
        self._last_click_time = 0.0
        self._click_debounce_sec = 0.20

    def poll(self):
        current_steps = self.encoder.steps
        delta = current_steps - self._last_steps

        if delta != 0:
            is_next = delta > 0

            if self._invert_rotation:
                is_next = not is_next

            if is_next:
                self._next = True
            else:
                self._previous = True

        self._last_steps = current_steps

        pressed = self.button.is_pressed

        if pressed and not self._last_button_pressed:
            now = time.monotonic()

            if now - self._last_click_time >= self._click_debounce_sec:
                self._last_click_time = now
                self._click = True

        self._last_button_pressed = pressed

    def close(self):
        try:
            self.encoder.close()
        except Exception:
            pass

        try:
            self.button.close()
        except Exception:
            pass

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
