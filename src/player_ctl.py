"""Sterownik odtwarzania: QMediaPlayer + stan bieżącej książki, bez widgetów.

Wydzielony z okna głównego, żeby logikę (brakujące pliki, wznawianie, zapis postępu,
rozdziały, prędkość, usypianie, zakładki, statystyki) dało się testować bez GUI.

Najważniejsze gwarancje:
- brakujący plik NIGDY nie zostawia odtwarzacza przy źródle poprzedniej książki
  (poprzednio: stary dźwięk grał pod nową książką i nadpisywał jej postęp);
- postęp nie jest zapisywany, dopóki nie zastosowano zapamiętanej pozycji (seek),
  więc zamknięcie programu tuż po starcie nie zeruje pozycji;
- ikona Play/Pauza wynika wyłącznie ze stanu odtwarzacza (`stateChanged`).
"""
import logging
import os
import time
import uuid

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from i18n import tr
from util import fmt_ms

log = logging.getLogger("audiobookplayer")

PS = QMediaPlayer.PlaybackState
MS = QMediaPlayer.MediaStatus

#: (minimalna przerwa w s, cofnięcie w ms) — po dłuższej przerwie cofamy o kilka sekund,
#: żeby przypomnieć sobie wątek; wybierany jest pierwszy pasujący (od najdłuższej).
REWIND_TIERS = [(1800, 30000), (600, 20000), (60, 10000), (10, 3000)]
FADE_STEPS = 12
FADE_INTERVAL_MS = 400


def rewind_for_gap(gap_seconds):
    for threshold, ms in REWIND_TIERS:
        if gap_seconds >= threshold:
            return ms
    return 0


class PlayerController(QObject):
    stateChanged = pyqtSignal(bool)          # True = gra
    bookChanged = pyqtSignal(object)         # bieżąca książka albo None
    fileChanged = pyqtSignal()               # zmienił się plik/rozdział
    positionChanged = pyqtSignal(int, int)   # pozycja i długość bieżącego pliku [ms]
    libraryChanged = pyqtSignal()            # trzeba odświeżyć listę książek
    speedChanged = pyqtSignal(float)
    message = pyqtSignal(str)
    sleepChanged = pyqtSignal(int)           # s do końca; -1 wyłączony; -2 „do końca pliku"

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(float(library.settings.get("volume", 0.9)))

        self.current = None
        self.pending_seek = None
        self._ready = False                  # zastosowano pozycję startową bieżącego pliku
        self._paused_at = None
        self._last_tick = None
        self._save_warned = False

        self.sleep_end_of_file = False
        self._sleep_deadline = None
        self._fade_step_no = 0
        self._fade_from = None

        self.player.positionChanged.connect(self._on_position)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(self._on_error)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.durationChanged.connect(self._on_duration)

        self._autosave = QTimer(self, interval=5000)
        self._autosave.timeout.connect(self.save_progress)
        self._sleep_timer = QTimer(self, interval=1000)
        self._sleep_timer.timeout.connect(self._sleep_tick)
        self._fade_timer = QTimer(self, interval=FADE_INTERVAL_MS)
        self._fade_timer.timeout.connect(self._fade_step)

    # ------------------------------------------------------------ ustawienia

    @property
    def auto_rewind(self):
        return bool(self.library.settings.get("auto_rewind", True))

    @property
    def per_book_speed(self):
        return bool(self.library.settings.get("per_book_speed", True))

    @property
    def is_playing(self):
        return self.player.playbackState() == PS.PlayingState

    def rate_for(self, book):
        if self.per_book_speed and book and book.get("speed"):
            return float(book["speed"])
        return float(self.library.settings.get("speed", 1.0))

    # ------------------------------------------------------------ otwieranie plików

    def _abort_playback(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.current = None
        self.pending_seek = None
        self._ready = False
        self._autosave.stop()
        self._cancel_fade()
        self.bookChanged.emit(None)

    def _open(self, book, index, seek_ms):
        """Ładuje plik `index` książki; brakujące pliki pomija. False = nic nie da się
        odtworzyć (odtwarzacz zostaje zatrzymany, nigdy przy starym źródle)."""
        files = book["files"]
        i, skipped = index, 0
        while i < len(files) and not os.path.exists(files[i]):
            i += 1
            skipped += 1
        if i >= len(files):
            self.message.emit(tr("err_no_files", title=book["title"]))
            self._abort_playback()
            return False
        if skipped:
            self.message.emit(tr("skipped_missing", n=skipped))
            seek_ms = 0
            book["position_ms"] = 0
        book["file_index"] = i
        self.current = book
        self._ready = False
        self.pending_seek = seek_ms if seek_ms > 0 else None
        self.player.setSource(QUrl.fromLocalFile(files[i]))
        self.player.setPlaybackRate(self.rate_for(book))
        self.fileChanged.emit()
        return True

    # ------------------------------------------------------------ sterowanie

    def play_book(self, book, restart=False):
        self.save_progress()
        if restart or book.get("finished"):
            book.update(file_index=0, position_ms=0, finished=False)
        start = int(book.get("position_ms", 0))
        last = book.get("last_played_at") or 0
        if self.auto_rewind and start > 0 and last:
            start = max(0, start - rewind_for_gap(time.time() - last))
        self._cancel_fade()
        if not self._open(book, book["file_index"], start):
            return False
        book["last_played_at"] = time.time()
        self.player.play()
        self._autosave.start()
        self.bookChanged.emit(book)         # odbiorca odświeża też listę książek
        self.speedChanged.emit(self.rate_for(book))
        return True

    def pause(self):
        if self.is_playing:
            self.player.pause()
            self.save_progress()

    def resume(self):
        if not self.current:
            return
        self._cancel_fade()
        if self.auto_rewind and self._paused_at:
            back = rewind_for_gap(time.time() - self._paused_at)
            if back:
                self.player.setPosition(max(0, self.player.position() - back))
        self.player.play()

    def toggle(self):
        if self.is_playing:
            self.pause()
        elif self.current:
            self.resume()

    def stop(self, save=True):
        if save:
            self.save_progress()
        self._abort_playback()
        self.stateChanged.emit(False)

    def skip(self, delta_ms):
        if self.current:
            self.player.setPosition(max(0, self.player.position() + delta_ms))

    def seek_in_file(self, ms):
        if self.current:
            self.player.setPosition(max(0, ms))

    def jump_to(self, book, file_index, start_ms=0):
        """Skok do rozdziału/zakładki — także w innej książce."""
        if book is not self.current:
            self.save_progress()            # nie gub postępu poprzedniej książki
        elif file_index == book["file_index"] and self._ready:
            self.player.setPosition(max(0, start_ms))
            if not self.is_playing:
                self.resume()
            return True
        book["file_index"], book["position_ms"] = file_index, start_ms
        if self._open(book, file_index, start_ms):
            book["last_played_at"] = time.time()
            self.player.play()
            self._autosave.start()
            self.bookChanged.emit(book)
            self.speedChanged.emit(self.rate_for(book))
            return True
        return False

    def next_file(self, pause_after=False):
        b = self.current
        if not b:
            return
        nxt = b["file_index"] + 1
        if nxt >= len(b["files"]):
            self.finish_book()
            return
        b["position_ms"] = 0
        if self._open(b, nxt, 0):
            self.player.pause() if pause_after else self.player.play()

    def prev_file(self):
        b = self.current
        if not b:
            return
        if self.player.position() > 5000 or b["file_index"] == 0:
            self.player.setPosition(0)
        else:
            b["position_ms"] = 0
            if self._open(b, b["file_index"] - 1, 0):
                self.player.play()

    def finish_book(self):
        book = self.current
        self.stop(save=False)
        if book:
            book.update(finished=True, file_index=0, position_ms=0,
                        last_played_at=time.time())
            self.library.save()
            self.libraryChanged.emit()
            self.message.emit(tr("finished_msg", title=book["title"]))

    # ------------------------------------------------------------ prędkość, głośność

    def set_speed(self, rate):
        rate = float(rate)
        self.player.setPlaybackRate(rate)
        self.library.settings["speed"] = rate      # domyślna dla nowych książek
        if self.per_book_speed and self.current:
            self.current["speed"] = rate
        self.speedChanged.emit(rate)

    def set_volume(self, value):
        self.audio.setVolume(max(0.0, min(1.0, value)))

    # ------------------------------------------------------------ zapis postępu

    def save_progress(self):
        b = self.current
        # dopóki nie zastosowano pozycji startowej, player.position() to 0 — zapis
        # zeruje zapamiętane miejsce (zamknięcie programu tuż po starcie)
        if not b or not self._ready or self.pending_seek is not None:
            return
        if not self.player.source().isValid():
            return
        b["position_ms"] = self.player.position()
        b["last_played_at"] = time.time()
        self.library.settings["volume"] = self.audio.volume()
        if self.library.save():
            self._save_warned = False
        elif not self._save_warned:
            self._save_warned = True
            self.message.emit(tr("save_failed", err=self.library.last_save_error or ""))

    # ------------------------------------------------------------ zakładki

    def add_bookmark(self, title=None):
        b = self.current
        if not b or not self._ready:
            return None
        pos = self.player.position()
        entry = {
            "id": uuid.uuid4().hex[:8],
            "file_index": b["file_index"],
            "position_ms": pos,
            "title": (title or "").strip()
                     or tr("bookmark_default", time=fmt_ms(b.offset_ms() + pos)),
            "created": time.time(),
        }
        b["bookmarks"].append(entry)
        b["bookmarks"].sort(key=lambda e: (e["file_index"], e["position_ms"]))
        self.library.save()
        self.libraryChanged.emit()
        self.message.emit(tr("bookmark_added", title=entry["title"]))
        return entry

    # ------------------------------------------------------------ usypianie

    def start_sleep(self, minutes=None, end_of_file=False):
        self.cancel_sleep(silent=True)
        if end_of_file:
            self.sleep_end_of_file = True
            self.sleepChanged.emit(-2)
        elif minutes:
            self._sleep_deadline = time.monotonic() + minutes * 60
            self._sleep_timer.start()
            self.sleepChanged.emit(minutes * 60)

    def cancel_sleep(self, silent=False):
        self._sleep_timer.stop()
        self._sleep_deadline = None
        self.sleep_end_of_file = False
        self._cancel_fade()
        if not silent:
            self.sleepChanged.emit(-1)

    def _sleep_tick(self):
        remaining = int(self._sleep_deadline - time.monotonic()) if self._sleep_deadline else 0
        if remaining > 0:
            self.sleepChanged.emit(remaining)
            return
        self._sleep_timer.stop()
        self._sleep_deadline = None
        if self.is_playing:
            self._fade_from = self.audio.volume()
            self._fade_step_no = FADE_STEPS
            self._fade_timer.start()
        else:
            self.sleepChanged.emit(-1)

    def _fade_step(self):
        self._fade_step_no -= 1
        if self._fade_step_no > 0:
            self.audio.setVolume(self._fade_from * self._fade_step_no / FADE_STEPS)
            return
        self._fade_timer.stop()
        self.player.pause()
        self.audio.setVolume(self._fade_from)
        self._fade_from = None
        self.save_progress()
        self.sleepChanged.emit(-1)
        self.message.emit(tr("sleep_stopped"))

    def _cancel_fade(self):
        if self._fade_timer.isActive():
            self._fade_timer.stop()
        if self._fade_from is not None:
            self.audio.setVolume(self._fade_from)   # przywróć głośność
            self._fade_from = None

    # ------------------------------------------------------------ zdarzenia odtwarzacza

    def _on_state(self, state):
        playing = state == PS.PlayingState
        if not playing and self.current:
            self._paused_at = time.time()
        self._last_tick = None
        self.stateChanged.emit(playing)

    def _on_status(self, status):
        if status in (MS.LoadedMedia, MS.BufferedMedia) and not self._ready:
            if self.pending_seek is not None:
                self.player.setPosition(self.pending_seek)
                self.pending_seek = None
            self._ready = True
        elif status == MS.EndOfMedia:
            if self.sleep_end_of_file:
                self.sleep_end_of_file = False
                self.sleepChanged.emit(-1)
                self.next_file(pause_after=True)
                self.message.emit(tr("sleep_stopped"))
            else:
                self.next_file()

    def _on_error(self, _err, text):
        log.warning("Błąd odtwarzania: %s", text)
        self.message.emit(tr("play_error", err=text))

    def _on_duration(self, duration):
        b = self.current
        if b and duration > 0:
            durs = b["durations"]
            i = b["file_index"]
            if i < len(durs) and durs[i] == 0:      # mutagen nie znał długości
                durs[i] = int(duration)
                self.libraryChanged.emit()

    def _on_position(self, pos):
        now = time.monotonic()
        if (self._last_tick is not None and self.current and self.is_playing
                and 0 < now - self._last_tick < 2.0):
            self.library.record_listening(self.current, int((now - self._last_tick) * 1000))
        self._last_tick = now
        self.positionChanged.emit(pos, self.player.duration())
