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

# Revisar la carpeta cada 15 segundos
PHOTO_REFRESH_INTERVAL = 15_000


def load_images(folder):
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    return [
        os.path.join(folder, f)
        for f in sorted(os.listdir(folder))
        if f.lower().endswith(SUPPORTED_EXTENSIONS)
    ]


def load_and_scale_image(path, screen_width, screen_height):
    with Image.open(path) as image:

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
            background=True
        )

    current_index = 0
    slideshow_running = False

    last_slide_change = pygame.time.get_ticks()
    last_photo_refresh = pygame.time.get_ticks()

    clock = pygame.time.Clock()

    # Cache de la imagen actualmente renderizada
    current_image_path = None
    image_surface = None

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

        now = pygame.time.get_ticks()

        # ---------------------------------
        # REFRESH PHOTO LIST
        # ---------------------------------

        if now - last_photo_refresh >= PHOTO_REFRESH_INTERVAL:

            new_images = load_images(PHOTO_FOLDER)

            if new_images != images:

                print(
                    f"Photos updated: "
                    f"{len(images)} -> {len(new_images)}"
                )

                # Intentamos mantener la misma foto
                # si todavía existe
                old_current_image = None

                if images and current_index < len(images):
                    old_current_image = images[current_index]

                images = new_images

                if images:

                    if (
                        old_current_image
                        and old_current_image in images
                    ):
                        current_index = images.index(
                            old_current_image
                        )

                    elif current_index >= len(images):
                        current_index = 0

                else:
                    current_index = 0

                # Fuerza recarga visual
                current_image_path = None
                image_surface = None

            last_photo_refresh = now

        # ---------------------------------
        # NO PHOTOS
        # ---------------------------------

        if not images:

            screen.fill((0, 0, 0))

            pygame.display.set_caption(
                "No photos available"
            )

            pygame.display.flip()

            # Seguimos procesando eventos
            # para poder salir correctamente
            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    shutdown()

                if event.type == pygame.KEYDOWN:

                    if event.key == pygame.K_ESCAPE:
                        shutdown()

            controller.update()

            clock.tick(30)

            continue

        # ---------------------------------
        # SLIDESHOW
        # ---------------------------------

        if slideshow_running:

            if (
                now - last_slide_change
                >= SLIDESHOW_INTERVAL
            ):

                current_index = next_image(
                    current_index,
                    len(images)
                )

                last_slide_change = now

        # ---------------------------------
        # LOAD IMAGE ONLY WHEN NECESSARY
        # ---------------------------------

        selected_image = images[current_index]

        if selected_image != current_image_path:

            try:
                image_surface = load_and_scale_image(
                    selected_image,
                    screen_width,
                    screen_height
                )

                current_image_path = selected_image

                print(
                    f"Loaded: {selected_image}"
                )

            except Exception as exc:

                print(
                    f"Error loading "
                    f"{selected_image}: {exc}"
                )

                current_index = next_image(
                    current_index,
                    len(images)
                )

                current_image_path = None

                clock.tick(30)

                continue

        # ---------------------------------
        # DRAW IMAGE
        # ---------------------------------

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

            last_slide_change = (
                pygame.time.get_ticks()
            )

            print(
                f"Previous -> {current_index + 1}"
            )

        if controller.next():

            current_index = next_image(
                current_index,
                len(images)
            )

            last_slide_change = (
                pygame.time.get_ticks()
            )

            print(
                f"Next -> {current_index + 1}"
            )

        if controller.click():

            slideshow_running = (
                not slideshow_running
            )

            last_slide_change = (
                pygame.time.get_ticks()
            )

            print(
                f"Slideshow: "
                f"{'PLAY' if slideshow_running else 'PAUSE'}"
            )

        clock.tick(30)


if __name__ == "__main__":
    main()