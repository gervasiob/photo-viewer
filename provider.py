import os
import pygame

from PIL import Image, ImageOps

try:
    import vlc as _vlc
except Exception:
    _vlc = None


def ensure_pygame_window_foreground():
    """
    Force the pygame window back to the foreground after VLC (or the WM)
    may have hidden/minimized it. Important: we intentionally do NOT call
    pygame.display.iconify() because that temporarily hides the window
    (causing a black screen) and on some WMs it never returns.
    """
    try:
        flags = getattr(pygame, "FULLSCREEN", 0)
        screen = pygame.display.get_surface()
        if screen is None:
            return
        size = screen.get_size()
        try:
            bpp = pygame.display.get_bpp()
        except Exception:
            try:
                bpp = getattr(pygame.display, "get_bpp", lambda: 32)()
            except Exception:
                bpp = 32
        pygame.display.set_mode(size, flags, bpp)
    except Exception:
        pass
    try:
        pygame.display.update()
    except Exception:
        pass


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
    def __init__(self, path, screen_width, screen_height, display_ms=None):
        self.path = path
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._surface = None
        self._draw_xy = (0, 0)
        self.DISPLAY_MS = int(display_ms if display_ms is not None else IMAGE_DISPLAY_MS)

    def load(self):
        with Image.open(self.path) as image:
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass

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

        self._instance = None
        self._player = None
        self._media = None
        self._draw_xy = (0, 0)
        self._video_size = None
        self._loaded = False
        self._finished = False
        self._started = False

    def load(self):
        if _vlc is None:
            raise RuntimeError(
                "python-vlc is not installed. "
                "Install it with: pip install python-vlc "
                "and make sure VLC is installed on this system."
            )

        self._instance = _vlc.Instance()
        self._player = self._instance.media_player_new()
        self._media = self._instance.media_new(self.path)
        self._player.set_media(self._media)

        display_info = pygame.display.Info()
        try:
            wid = display_info.wm_window
        except Exception:
            wid = 0

        if wid:
            if os.name == "nt":
                self._player.set_hwnd(wid)
            else:
                try:
                    self._player.set_xwindow(wid)
                except Exception:
                    pass

        self._video_size = compute_fit_size(
            1920,
            1080,
            self.screen_width,
            self.screen_height,
            only_shrink=True,
        )

        self._draw_xy = _center_xy(
            self.screen_width,
            self.screen_height,
            self._video_size[0],
            self._video_size[1],
        )

        self._loaded = True

    def start(self):
        self._finished = False
        self._started = False
        if self._player is not None:
            self._player.play()
            self._started = True

    def is_finished(self):
        if self._finished:
            return True
        if self._player is None:
            return True
        if not self._started:
            return False
        state = self._player.get_state()
        finished_states = (
            _vlc.State.Ended if _vlc is not None else None,
            _vlc.State.Stopped if _vlc is not None else None,
            _vlc.State.Error if _vlc is not None else None,
        )
        return state in [s for s in finished_states if s is not None]

    def toggle_pause(self):
        if self._player is None:
            return
        self._player.pause()

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
        if self._player is not None:
            try:
                self._player.set_hwnd(0)
            except Exception:
                pass
            try:
                self._player.set_xwindow(0)
            except Exception:
                pass
            try:
                self._player.set_nsobject(0)
            except Exception:
                pass
            try:
                self._player.stop()
            except Exception:
                pass
            try:
                self._player.release()
            except Exception:
                pass
        if self._media is not None:
            try:
                self._media.release()
            except Exception:
                pass
        if self._instance is not None:
            try:
                self._instance.release()
            except Exception:
                pass
        self._player = None
        self._media = None
        self._instance = None
        ensure_pygame_window_foreground()


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


def create_provider(
    file_type,
    path,
    screen_width,
    screen_height,
    image_display_ms=None,
):
    if file_type == FILE_TYPE_IMAGE:
        return ImageProvider(
            path,
            screen_width,
            screen_height,
            display_ms=image_display_ms,
        )
    if file_type == FILE_TYPE_VIDEO:
        return VideoProvider(path, screen_width, screen_height)
    if file_type == FILE_TYPE_AUDIO:
        return AudioProvider(path, screen_width, screen_height)
    raise ValueError(f"Unsupported file type: {file_type}")
