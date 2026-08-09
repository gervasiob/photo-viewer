import sys
import os
import pygame

try:
    os.environ.setdefault("SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR", "0")
except Exception:
    pass

from controllers import KnobInputController, MenuKnobController
from provider import PlaybackResult, ensure_pygame_window_foreground
from service import MediaService
from settings_model import Settings
from menu_controller import MenuController

try:
    from gpiozero import LED
except Exception:
    LED = None


MEDIA_FOLDER = "photos"
STATUS_LED_PIN = 22


def _status_title(service, menu):
    if menu.open:
        return "Settings"

    if not service.has_media():
        return "No media available"

    state = "PLAY" if service.slideshow_running() else "PAUSE"
    current = service.current_index() + 1
    total = service.total_count()

    return f"Media {current}/{total} {state}"


def main():
    pygame.init()

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Baby Girl Photo Frame")

    screen_width, screen_height = screen.get_size()

    settings = Settings.load()

    service = MediaService(
        folder=MEDIA_FOLDER,
        screen_width=screen_width,
        screen_height=screen_height,
        auto_play=True,
        settings=settings,
    )
    service.refresh(force=True)

    menu = MenuController(screen_width, screen_height)

    nav_controller = KnobInputController()
    menu_controller = MenuKnobController()
    status_led = None

    if LED is not None:
        try:
            status_led = LED(STATUS_LED_PIN)
        except Exception:
            status_led = None

    if status_led is not None:
        status_led.blink(
            on_time=0.2,
            off_time=0.2,
            background=True,
        )

    clock = pygame.time.Clock()

    def shutdown():
        try:
            service.close()
        except Exception:
            pass
        try:
            nav_controller.close()
        except Exception:
            pass
        try:
            menu_controller.close()
        except Exception:
            pass
        if status_led is not None:
            try:
                status_led.off()
                status_led.close()
            except Exception:
                pass
        pygame.quit()
        sys.exit()

    while True:
        pygame.event.pump()

        in_menu = menu.open

        if not in_menu:
            service.tick()
            service.draw(screen)
        else:
            service.draw(screen)
            menu.draw(screen)

        pygame.display.set_caption(_status_title(service, menu))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                shutdown()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if in_menu:
                        menu.close_menu(save=False)
                    else:
                        shutdown()
                elif in_menu:
                    menu.handle_event(event)
                else:
                    provider_result = service.handle_event(event)
                    if provider_result == PlaybackResult.NEXT:
                        service.next()
                    elif provider_result == PlaybackResult.PREV:
                        service.previous()
                    elif provider_result == PlaybackResult.TOGGLE_PLAY:
                        service.toggle_slideshow()

        nav_controller.update()

        menu_controller.update()

        was_in_menu = in_menu

        if in_menu:
            if menu_controller.wheel_up():
                menu.handle_wheel_up()
            if menu_controller.wheel_down():
                menu.handle_wheel_down()
            if menu_controller.ok():
                menu.handle_ok()
            if menu_controller.back():
                menu.handle_back()
        else:
            if nav_controller.menu():
                menu.open_menu()
            if nav_controller.previous():
                service.previous()
            if nav_controller.next():
                service.next()
            if nav_controller.click():
                service.toggle_slideshow()

        # If we just exited the menu (Save or Cancel), re-focus the pygame window
        if was_in_menu and not menu.open:
            settings_after_save = menu.effective_settings()
            if settings_after_save.order != service.settings.order or (
                settings_after_save.image_display_ms
                != service.settings.image_display_ms
            ):
                service.apply_settings(settings_after_save)
            ensure_pygame_window_foreground()

        # If we just entered the menu from playback, also re-focus to avoid
        # VLC output lingering or window going behind the desktop.
        if (not was_in_menu) and menu.open:
            ensure_pygame_window_foreground()

        clock.tick(30)


if __name__ == "__main__":
    main()
