import sys
import pygame

from input_controller import PhotoFrameController
from provider import PlaybackResult
from service import MediaService

try:
    from gpiozero import LED
except Exception:
    LED = None


MEDIA_FOLDER = "photos"
STATUS_LED_PIN = 22


def _status_title(service):
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

    service = MediaService(
        folder=MEDIA_FOLDER,
        screen_width=screen_width,
        screen_height=screen_height,
        auto_play=True,
    )
    service.refresh(force=True)

    controller = PhotoFrameController()
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
            controller.close()
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
        service.tick()
        service.draw(screen)

        pygame.display.set_caption(_status_title(service))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                shutdown()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    shutdown()

            provider_result = service.handle_event(event)
            if provider_result == PlaybackResult.NEXT:
                service.next()
            elif provider_result == PlaybackResult.PREV:
                service.previous()
            elif provider_result == PlaybackResult.TOGGLE_PLAY:
                service.toggle_slideshow()

        controller.update()

        if controller.previous():
            service.previous()

        if controller.next():
            service.next()

        if controller.click():
            service.toggle_slideshow()

        clock.tick(30)


if __name__ == "__main__":
    main()
