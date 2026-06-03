import os
import sys
import pygame

from PIL import Image

from input_controller import PhotoFrameController

try:
    from gpiozero import LED
except Exception:
    LED = None


PHOTO_FOLDER = "photos"
STATUS_LED_PIN = 22

SUPPORTED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
)

SLIDESHOW_INTERVAL = 1000


def load_images(folder):
    return [
        os.path.join(folder, f)
        for f in sorted(os.listdir(folder))
        if f.lower().endswith(SUPPORTED_EXTENSIONS)
    ]


def load_and_scale_image(path, screen_width, screen_height):
    image = Image.open(path)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    image_width, image_height = image.size

    scale = min(
        screen_width / image_width,
        screen_height / image_height,
        1.0
    )

    if scale < 1.0:
        new_size = (
            max(1, int(image_width * scale)),
            max(1, int(image_height * scale)),
        )

        image = image.resize(
            new_size,
            Image.Resampling.LANCZOS
        )

    mode = image.mode
    size = image.size
    data = image.tobytes()

    return pygame.image.fromstring(
        data,
        size,
        mode
    )


def next_image(current, total):
    return (current + 1) % total


def prev_image(current, total):
    return (current - 1) % total


def main():

    pygame.init()

    screen = pygame.display.set_mode(
        (0, 0),
        pygame.FULLSCREEN
    )

    pygame.display.set_caption(
        "Baby Girl Photo Frame"
    )

    screen_width, screen_height = screen.get_size()

    images = load_images(PHOTO_FOLDER)

    if not images:
        print(
            "Noooooo, sorry my love. "
            "Find me another folder with photos."
        )
        return

    controller = PhotoFrameController()
    status_led = LED(STATUS_LED_PIN) if LED is not None else None

    if status_led is not None:
        status_led.blink(
            on_time=0.2,
            off_time=0.2,
            background=True
        )

    current_index = 0
    slideshow_running = False

    last_slide_change = pygame.time.get_ticks()

    clock = pygame.time.Clock()

    def shutdown():
        controller.close()
        if status_led is not None:
            try:
                status_led.off()
                status_led.close()
            except Exception:
                pass
        pygame.quit()
        sys.exit()

    while True:

        # ---------------------------------
        # SLIDESHOW
        # ---------------------------------

        if slideshow_running:

            now = pygame.time.get_ticks()

            if now - last_slide_change >= SLIDESHOW_INTERVAL:

                current_index = next_image(
                    current_index,
                    len(images)
                )

                last_slide_change = now

        # ---------------------------------
        # LOAD IMAGE
        # ---------------------------------

        image_surface = load_and_scale_image(
            images[current_index],
            screen_width,
            screen_height
        )

        screen.fill((0, 0, 0))

        x = (
            screen_width
            - image_surface.get_width()
        ) // 2

        y = (
            screen_height
            - image_surface.get_height()
        ) // 2

        screen.blit(
            image_surface,
            (x, y)
        )

        pygame.display.set_caption(
            f"Photo {current_index + 1}/{len(images)} "
            f"{'PLAY' if slideshow_running else 'PAUSE'}"
        )

        pygame.display.flip()

        # ---------------------------------
        # EVENTS
        # ---------------------------------

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                shutdown()

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    shutdown()

        # ---------------------------------
        # INPUT COMMANDS
        # ---------------------------------

        controller.update()

        if controller.previous():

            current_index = prev_image(
                current_index,
                len(images)
            )

            last_slide_change = pygame.time.get_ticks()

            print(
                f"Previous -> {current_index + 1}"
            )

        if controller.next():

            current_index = next_image(
                current_index,
                len(images)
            )

            last_slide_change = pygame.time.get_ticks()

            print(
                f"Next -> {current_index + 1}"
            )

        if controller.click():

            slideshow_running = (
                not slideshow_running
            )

            print(
                f"Slideshow: "
                f"{'PLAY' if slideshow_running else 'PAUSE'}"
            )

        clock.tick(30)


if __name__ == "__main__":
    main()
