import os
import pygame

from PIL import Image


IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
    ".gif",
)

VIDEO_EXTENSIONS = (
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
)

AUDIO_EXTENSIONS = (
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".aac",
    ".m4a",
)

IMAGE_DISPLAY_MS = 5_000

FILE_TYPE_IMAGE = "image"
FILE_TYPE_VIDEO = "video"
FILE_TYPE_AUDIO = "audio"
FILE_TYPE_UNKNOWN = "unknown"


def detect_file_type(path):
    ext = os.path.splitext(path)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        return FILE_TYPE_IMAGE
    if ext in VIDEO_EXTENSIONS:
        return FILE_TYPE_VIDEO
    if ext in AUDIO_EXTENSIONS:
        return FILE_TYPE_AUDIO
    return FILE_TYPE_UNKNOWN


def compute_fit_size(
    source_width,
    source_height,
    screen_width,
    screen_height,
    only_shrink=True,
):
    if source_width <= 0 or source_height <= 0:
        return (0, 0)

    scale = min(
        screen_width / source_width,
        screen_height / source_height,
    )

    if only_shrink and scale > 1.0:
        scale = 1.0

    return (
        max(1, int(source_width * scale)),
        max(1, int(source_height * scale)),
    )


def _center_xy(screen_width, screen_height, surface_width, surface_height):
    x = (screen_width - surface_width) // 2
    y = (screen_height - surface_height) // 2
    return x, y


def _pygame_surface_from_pil(image):
    if image.mode == "RGB":
        mode = "RGB"
    else:
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")
        mode = image.mode

    data = image.tobytes()
    return pygame.image.fromstring(data, image.size, mode)


class PlaybackResult:
    SKIP = "skip"
    NEXT = "next"
    PREV = "previous"
    TOGGLE_PLAY = "toggle_play"
    QUIT = "quit"


class ImageProvider:
    DISPLAY_MS = IMAGE_DISPLAY_MS

    def __init__(self, path, screen_width, screen_height):
        self.path = path
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._surface = None
        self._draw_xy = (0, 0)

    def load(self):
        with Image.open(self.path) as image:
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")

            new_size = compute_fit_size(
                image.size[0],
                image.size[1],
                self.screen_width,
                self.screen_height,
                only_shrink=True,
            )

            if new_size != image.size:
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            self._surface = _pygame_surface_from_pil(image)

        self._draw_xy = _center_xy(
            self.screen_width,
            self.screen_height,
            self._surface.get_width(),
            self._surface.get_height(),
        )

    def start(self):
        self._start_ticks = pygame.time.get_ticks()
        self._paused = False
        self._paused_at = None

    def is_finished(self):
        if self._paused:
            return False
        elapsed = pygame.time.get_ticks() - self._start_ticks
        return elapsed >= self.DISPLAY_MS

    def toggle_pause(self):
        if self._paused:
            paused_for = pygame.time.get_ticks() - self._paused_at
            self._start_ticks += paused_for
            self._paused = False
            self._paused_at = None
        else:
            self._paused = True
            self._paused_at = pygame.time.get_ticks()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            return PlaybackResult.NEXT
        return None

    def handle_command(self, command):
        if command == PlaybackResult.NEXT:
            return PlaybackResult.NEXT
        if command == PlaybackResult.PREV:
            return PlaybackResult.PREV
        if command == PlaybackResult.TOGGLE_PLAY:
            self.toggle_pause()
            return PlaybackResult.TOGGLE_PLAY
        return None

    def update(self):
        return None

    def draw(self, screen):
        screen.fill((0, 0, 0))
        screen.blit(self._surface, self._draw_xy)

    def close(self):
        self._surface = None


class VideoProvider:
    def __init__(self, path, screen_width, screen_height):
        self.path = path
        self.screen_width = screen_width
        self.screen_height = screen_height

        self._movie = None
        self._movie_size = None
        self._draw_xy = (0, 0)
        self._loaded = False
        self._finished = False

    def load(self):
        if not hasattr(pygame, "movie"):
            raise RuntimeError(
                "pygame.movie is not available in this build. "
                "Rebuild pygame with movie support or install a version "
                "that ships the movie module."
            )

        self._movie = pygame.movie.Movie(self.path)

        video_size = self._movie.get_size()
        self._movie_size = compute_fit_size(
            video_size[0],
            video_size[1],
            self.screen_width,
            self.screen_height,
            only_shrink=True,
        )

        self._draw_xy = _center_xy(
            self.screen_width,
            self.screen_height,
            self._movie_size[0],
            self._movie_size[1],
        )

        self._movie.set_display(None, pygame.Rect(
            self._draw_xy[0],
            self._draw_xy[1],
            self._movie_size[0],
            self._movie_size[1],
        ))
        self._loaded = True

    def start(self):
        self._finished = False
        if self._movie is not None:
            self._movie.play()

    def is_finished(self):
        if self._finished:
            return True
        if self._movie is None:
            return True
        if self._movie.get_busy():
            return False
        return True

    def toggle_pause(self):
        if self._movie is None:
            return
        if self._movie.get_busy():
            self._movie.pause()
        else:
            self._movie.play()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._finished = True
            return PlaybackResult.NEXT
        return None

    def handle_command(self, command):
        if command == PlaybackResult.NEXT:
            self._finished = True
            return PlaybackResult.NEXT
        if command == PlaybackResult.PREV:
            self._finished = True
            return PlaybackResult.PREV
        if command == PlaybackResult.TOGGLE_PLAY:
            self.toggle_pause()
            return PlaybackResult.TOGGLE_PLAY
        return None

    def update(self):
        return None

    def draw(self, screen):
        screen.fill((0, 0, 0))

    def close(self):
        if self._movie is not None:
            try:
                self._movie.stop()
            except Exception:
                pass
        self._movie = None


class AudioProvider:
    def __init__(self, path, screen_width, screen_height):
        self.path = path
        self.screen_width = screen_width
        self.screen_height = screen_height

        self._sound = None
        self._channel = None
        self._finished = False
        self._loaded = False

    def load(self):
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                pass

        if pygame.mixer.get_init():
            self._sound = pygame.mixer.Sound(self.path)
        self._loaded = True

    def start(self):
        self._finished = False
        if self._sound is not None:
            self._channel = self._sound.play()

    def is_finished(self):
        if self._finished:
            return True
        if self._channel is None:
            return True
        return not self._channel.get_busy()

    def toggle_pause(self):
        if self._channel is None:
            return
        if self._channel.get_busy():
            self._channel.pause()
        else:
            self._channel.unpause()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._finished = True
            return PlaybackResult.NEXT
        return None

    def handle_command(self, command):
        if command == PlaybackResult.NEXT:
            self._finished = True
            return PlaybackResult.NEXT
        if command == PlaybackResult.PREV:
            self._finished = True
            return PlaybackResult.PREV
        if command == PlaybackResult.TOGGLE_PLAY:
            self.toggle_pause()
            return PlaybackResult.TOGGLE_PLAY
        return None

    def update(self):
        return None

    def draw(self, screen):
        screen.fill((0, 0, 0))

    def close(self):
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass
        if self._sound is not None:
            try:
                self._sound.stop()
            except Exception:
                pass
        self._channel = None
        self._sound = None


def create_provider(file_type, path, screen_width, screen_height):
    if file_type == FILE_TYPE_IMAGE:
        return ImageProvider(path, screen_width, screen_height)
    if file_type == FILE_TYPE_VIDEO:
        return VideoProvider(path, screen_width, screen_height)
    if file_type == FILE_TYPE_AUDIO:
        return AudioProvider(path, screen_width, screen_height)
    raise ValueError(f"Unsupported file type: {file_type}")
