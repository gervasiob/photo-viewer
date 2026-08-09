import os
import pygame

from provider import (
    PlaybackResult,
    FILE_TYPE_UNKNOWN,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    detect_file_type,
    create_provider,
)


SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + AUDIO_EXTENSIONS

FOLDER_REFRESH_MS = 15_000


def _list_supported_files(folder):
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
        return []

    return sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(SUPPORTED_EXTENSIONS)
    )


class MediaService:
    def __init__(self, folder, screen_width, screen_height, auto_play=True):
        self.folder = folder
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.auto_play = auto_play

        self._files = []
        self._queue = []
        self._current_index = 0
        self._current_path = None
        self._current_type = FILE_TYPE_UNKNOWN
        self._current_provider = None

        self._last_refresh = pygame.time.get_ticks()
        self._slideshow_running = auto_play
        self._last_transition = pygame.time.get_ticks()
        self._advance_on_finish = False

        self._files = _list_supported_files(self.folder)
        self._queue = list(self._files)

    # ------------------------------------------------------------------
    # Public status helpers
    # ------------------------------------------------------------------

    def has_media(self):
        return bool(self._files)

    def current_path(self):
        return self._current_path

    def current_index(self):
        return self._current_index

    def total_count(self):
        return len(self._files)

    def slideshow_running(self):
        return self._slideshow_running

    def toggle_slideshow(self):
        self._slideshow_running = not self._slideshow_running
        if self._current_provider is not None:
            if self._current_type == "image":
                try:
                    self._current_provider.toggle_pause()
                except Exception:
                    pass
        return self._slideshow_running

    # ------------------------------------------------------------------
    # File list + queue management
    # ------------------------------------------------------------------

    def refresh(self, force=False):
        now = pygame.time.get_ticks()

        if (
            not force
            and now - self._last_refresh < FOLDER_REFRESH_MS
        ):
            return False

        self._last_refresh = now

        new_files = _list_supported_files(self.folder)

        if new_files == self._files:
            return False

        old_current = None
        if self._current_path and self._current_path in self._files:
            old_current = self._current_path

        self._files = new_files

        if not self._files:
            self._queue = []
            self._current_index = 0
            self._close_current()
            return True

        if old_current and old_current in self._files:
            self._current_index = self._files.index(old_current)
        elif self._current_index >= len(self._files):
            self._current_index = 0
        else:
            self._current_index = max(0, min(self._current_index, len(self._files) - 1))

        newly_seen = [p for p in self._files if p not in self._queue]
        self._queue.extend(newly_seen)
        self._queue = [p for p in self._queue if p in self._files]

        self._close_current()
        return True

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _step_index(self, step):
        if not self._files:
            return None
        self._current_index = (self._current_index + step) % len(self._files)
        return self._files[self._current_index]

    def _queue_next_from_folder(self):
        if not self._files:
            return None
        if not self._queue:
            self._queue = list(self._files)
        return self._queue.pop(0)

    def next(self):
        if not self._files:
            return False
        path = self._step_index(+1)
        return self._play(path, advance_on_finish=False)

    def previous(self):
        if not self._files:
            return False
        path = self._step_index(-1)
        return self._play(path, advance_on_finish=False)

    def autonext(self):
        if not self._files:
            return False
        path = self._step_index(+1)
        return self._play(path, advance_on_finish=True)

    def play_from_queue(self):
        path = self._queue_next_from_folder()
        if path is None:
            return False
        if path in self._files:
            self._current_index = self._files.index(path)
        else:
            self._files.append(path)
            self._current_index = len(self._files) - 1
        return self._play(path, advance_on_finish=True)

    # ------------------------------------------------------------------
    # Playback lifecycle
    # ------------------------------------------------------------------

    def _play(self, path, advance_on_finish=False):
        if path is None:
            return False

        file_type = detect_file_type(path)
        if file_type == FILE_TYPE_UNKNOWN:
            return False

        self._close_current()

        provider = None
        try:
            provider = create_provider(
                file_type,
                path,
                self.screen_width,
                self.screen_height,
            )
            provider.load()
        except Exception as exc:
            print(f"[MediaService] Failed to load {path}: {exc}")
            try:
                if provider is not None:
                    provider.close()
            except Exception:
                pass
            self._current_provider = None
            self._current_path = None
            self._current_type = FILE_TYPE_UNKNOWN
            return False

        self._current_provider = provider
        self._current_path = path
        self._current_type = file_type
        self._advance_on_finish = advance_on_finish

        try:
            provider.start()
        except Exception as exc:
            print(f"[MediaService] Failed to start {path}: {exc}")
            self._close_current()
            return False

        self._last_transition = pygame.time.get_ticks()
        print(f"[MediaService] Playing: {path} ({file_type})")
        return True

    def ensure_playing(self):
        if self._current_provider is not None:
            return True
        if not self.has_media():
            return False
        path = self._files[self._current_index]
        return self._play(path, advance_on_finish=self.auto_play)

    def _close_current(self):
        if self._current_provider is None:
            return
        try:
            self._current_provider.close()
        except Exception:
            pass
        self._current_provider = None
        self._current_path = None
        self._current_type = FILE_TYPE_UNKNOWN

    # ------------------------------------------------------------------
    # Event / command dispatch (called from main loop)
    # ------------------------------------------------------------------

    def handle_event(self, event):
        self.refresh(force=False)

        if self._current_provider is None:
            return None

        return self._current_provider.handle_event(event)

    def handle_command(self, command):
        if command == PlaybackResult.NEXT:
            return self.next()
        if command == PlaybackResult.PREV:
            return self.previous()
        if command == PlaybackResult.TOGGLE_PLAY:
            self.toggle_slideshow()
            if self._current_provider is not None:
                try:
                    self._current_provider.handle_command(PlaybackResult.TOGGLE_PLAY)
                except Exception:
                    pass
            return True
        return False

    # ------------------------------------------------------------------
    # Per-frame tick + draw
    # ------------------------------------------------------------------

    def tick(self):
        self.refresh(force=False)

        if not self.has_media():
            self._close_current()
            return None

        if self._current_provider is None:
            self.ensure_playing()
            return None

        try:
            self._current_provider.update()
        except Exception:
            pass

        if self._current_provider.is_finished():
            if self._slideshow_running or self._advance_on_finish:
                self.autonext()
        return None

    def draw(self, screen):
        if self._current_provider is None:
            screen.fill((0, 0, 0))
            return
        self._current_provider.draw(screen)

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def close(self):
        self._close_current()
