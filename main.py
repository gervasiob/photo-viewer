import sys
import os
import subprocess

try:
    os.environ.setdefault("SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR", "0")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Optional git pull self-update on startup (before importing our modules,
# so if we pull updated code we can re-exec with the new files).
# Set SKIP_GIT_PULL=1 to disable (useful on dev machines / no network).
# ---------------------------------------------------------------------------


WATCH_FOR_RELOAD_SUFFIXES = (".py",)


def _project_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _git_pull_on_startup():
    """
    Runs `git pull` in the project folder. Returns:
      - False: could not / did not update code (no git, no repo, no network,
               already up-to-date, skipped by env var).
      - True : files were pulled. Caller can re-exec to load the new code.
    """
    if os.environ.get("SKIP_GIT_PULL") in ("1", "true", "True", "yes", "YES"):
        return False

    try:
        project_root = _project_dir()
        if not os.path.exists(os.path.join(project_root, ".git")):
            return False
    except Exception:
        return False

    pull_kwargs = {
        "cwd": project_root,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
    }

    try:
        result = subprocess.run(["git", "pull", "--ff-only"], **pull_kwargs)
    except Exception as exc:
        print(f"[boot] git pull skipped: {exc}")
        return False

    output = (result.stdout or "").strip()
    if output:
        print("[boot] git pull output:\n" + output)

    if result.returncode != 0:
        print(f"[boot] git pull failed with code {result.returncode}; continuing anyway.")
        return False

    # Already up to date -> no restart required.
    if (
        "Already up to date" in output
        or "Already up-to-date" in output
    ):
        return False

    # Otherwise we assume the pull changed *something* on disk. For safety,
    # only cause a restart if any tracked .py file appears in the output or
    # if the result came from a fast-forward merge. The simpler/robust rule
    # used here is: restart unless git explicitly told us nothing changed.
    return True


def _restart_self():
    try:
        python = sys.executable or "python3"
    except Exception:
        python = "python3"
    argv = [python] + sys.argv
    print(f"[boot] Restarting with updated code: {' '.join(argv)}")
    try:
        os.execv(python, argv)
    except Exception:
        # execv might not be available on Windows; fall back to a plain exit
        # so a supervisor can restart us instead.
        sys.exit(0)


if __name__ == "__main__":
    # Important: we only self-update/restart on the *initial* invocation
    # (before running inner main() + heavy imports like pygame/service).
    # This guard also prevents an infinite restart loop after re-exec.
    if os.environ.get("__PHOTO_VIEWER_RESTARTED") != "1":
        try:
            updated = _git_pull_on_startup()
        except Exception as exc:
            updated = False
            print(f"[boot] self-update check failed, continuing: {exc}")
        if updated:
            os.environ["__PHOTO_VIEWER_RESTARTED"] = "1"
            _restart_self()

    main()


import pygame

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
        else:
            # Long-press the menu knob's own push button (>=0.5s) to open settings.
            # The nav menu GPIO (GPIO23) is still supported as an optional fallback.
            if menu_controller.open_menu_request():
                menu.open_menu()
            elif nav_controller.menu():
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
