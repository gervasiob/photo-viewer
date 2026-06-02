import pygame

from collections import deque
import threading
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

        self._lock = threading.Lock()
        self._actions = deque()

        self._gpio_enabled = False
        self._invert_rotation = invert_rotation
        self._clk_pin = clk_pin
        self._dt_pin = dt_pin
        self._sw_pin = sw_pin

        self._last_clk_state = 0
        self._last_rotate_time = 0.0
        self._rotate_debounce_sec = 0.002

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

        GPIO.add_event_detect(
            self._clk_pin,
            GPIO.BOTH,
            callback=self._on_clk_edge,
            bouncetime=1,
        )

        GPIO.add_event_detect(
            self._sw_pin,
            GPIO.FALLING,
            callback=self._on_switch_press,
            bouncetime=200,
        )

        self._gpio_enabled = True

    def close(self):
        if GPIO is None or not self._gpio_enabled:
            return

        try:
            GPIO.remove_event_detect(self._clk_pin)
        except Exception:
            pass

        try:
            GPIO.remove_event_detect(self._sw_pin)
        except Exception:
            pass

        try:
            GPIO.cleanup(
                (self._clk_pin, self._dt_pin, self._sw_pin)
            )
        except Exception:
            pass

        self._gpio_enabled = False

    def _enqueue_action(self, action):
        with self._lock:
            self._actions.append(action)

    def _on_clk_edge(self, _channel):
        clk_state = GPIO.input(self._clk_pin)

        if clk_state == self._last_clk_state:
            return

        self._last_clk_state = clk_state

        if clk_state != 1:
            return

        now = time.monotonic()

        if now - self._last_rotate_time < self._rotate_debounce_sec:
            return

        self._last_rotate_time = now

        dt_state = GPIO.input(self._dt_pin)
        is_next = (dt_state != clk_state)

        if self._invert_rotation:
            is_next = not is_next

        self._enqueue_action(
            "next" if is_next else "previous"
        )

    def _on_switch_press(self, _channel):
        self._enqueue_action("click")

    def _drain_actions(self):
        with self._lock:
            while self._actions:
                action = self._actions.popleft()

                if action == "previous":
                    self._pending_previous += 1
                elif action == "next":
                    self._pending_next += 1
                elif action == "click":
                    self._pending_click += 1

    def handle_event(self, event):
        self._keyboard.handle_event(event)

    def previous(self):
        if self._keyboard.previous():
            return True

        self._drain_actions()

        if self._pending_previous > 0:
            self._pending_previous -= 1
            return True

        return False

    def next(self):
        if self._keyboard.next():
            return True

        self._drain_actions()

        if self._pending_next > 0:
            self._pending_next -= 1
            return True

        return False

    def click(self):
        if self._keyboard.click():
            return True

        self._drain_actions()

        if self._pending_click > 0:
            self._pending_click -= 1
            return True

        return False
