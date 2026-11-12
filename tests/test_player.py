"""PlayerController na prawdziwym QMediaPlayer (cichy WAV, tryb offscreen)."""
import os
import time

import pytest

import library as lib
from conftest import make_wav
from models import Book
from player_ctl import MS, PlayerController, rewind_for_gap


pytestmark = pytest.mark.audio


@pytest.fixture
def ctl(qtbot, library):
    c = PlayerController(library)
    c.audio.setVolume(0.0)
    yield c
    c.stop(save=False)


def mkbook(library, audio_dir, name, files=1, seconds=3):
    paths = [make_wav(audio_dir / name / f"{i + 1:02d}.wav", seconds=seconds) for i in range(files)]
    b = Book.new(str(audio_dir / name), "folder", paths, title=name)
    b["durations"] = [seconds * 1000] * files
    library.books.append(b)
    return b


def ready(qtbot, ctl):
    qtbot.waitUntil(lambda: ctl._ready, timeout=8000)


# ---------------------------------------------------------------- B3: brakujący plik

def test_missing_file_never_leaves_previous_book_playing(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A")
    b = Book.new(str(audio_dir / "B"), "folder", [str(audio_dir / "B" / "nie_ma.mp3")], title="B")
    b["position_ms"] = 1234
    library.books.append(b)
    messages = []
    ctl.message.connect(messages.append)

    assert ctl.play_book(a)
    ready(qtbot, ctl)
    qtbot.waitUntil(lambda: ctl.player.position() > 300, timeout=5000)

    assert ctl.play_book(b) is False
    assert ctl.current is None                          # nie „B z dźwiękiem A"
    assert not ctl.player.source().isValid()            # źródło wyczyszczone
    assert ctl.player.playbackState().name != "PlayingState"
    assert b["position_ms"] == 1234                     # postęp B nietknięty
    assert a["position_ms"] > 0                         # postęp A zapisany przy przełączeniu
    assert any("Nie znaleziono plików" in m for m in messages)


def test_missing_leading_files_are_skipped(qtbot, ctl, library, audio_dir):
    real = make_wav(audio_dir / "C" / "02.wav", seconds=2)
    c = Book.new(str(audio_dir / "C"), "folder", [str(audio_dir / "C" / "01.wav"), real], title="C")
    c["position_ms"] = 900
    library.books.append(c)
    messages = []
    ctl.message.connect(messages.append)
    assert ctl.play_book(c)
    assert c["file_index"] == 1 and c["position_ms"] == 0
    assert ctl.pending_seek is None
    assert any("Pominięto" in m for m in messages)


# ---------------------------------------------------------------- zapis postępu

def test_no_progress_save_before_start_position_is_applied(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A")
    a["position_ms"] = 2000
    a["last_played_at"] = 0
    ctl.play_book(a)
    ctl.save_progress()                  # zamknięcie programu tuż po starcie
    assert a["position_ms"] == 2000      # NIE wyzerowane do 0
    ready(qtbot, ctl)
    qtbot.waitUntil(lambda: ctl.player.position() >= 1900, timeout=5000)


def test_resume_from_saved_position(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=4)
    a["position_ms"] = 2500
    library.settings["auto_rewind"] = False
    ctl.play_book(a)
    ready(qtbot, ctl)
    qtbot.waitUntil(lambda: ctl.player.position() >= 2400, timeout=5000)


def test_jump_to_other_book_saves_previous_progress(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=5)
    b = mkbook(library, audio_dir, "B", seconds=5)
    ctl.play_book(a)
    ready(qtbot, ctl)
    qtbot.waitUntil(lambda: ctl.player.position() > 500, timeout=5000)
    assert a["position_ms"] == 0
    ctl.jump_to(b, 0, 0)                              # B7: poprzednio gubiło postęp A
    assert a["position_ms"] > 0
    assert ctl.current is b


def test_save_failure_is_reported_once(qtbot, ctl, library, audio_dir, monkeypatch):
    a = mkbook(library, audio_dir, "A")
    ctl.play_book(a)
    ready(qtbot, ctl)
    monkeypatch.setattr(lib.os, "replace", lambda *x: (_ for _ in ()).throw(PermissionError("x")))
    messages = []
    ctl.message.connect(messages.append)
    ctl.save_progress()
    ctl.save_progress()
    assert len([m for m in messages if "zapisać" in m]) == 1


# ---------------------------------------------------------------- stan i nawigacja

def test_state_signal_follows_player(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=5)
    states = []
    ctl.stateChanged.connect(states.append)
    ctl.play_book(a)
    qtbot.waitUntil(lambda: True in states, timeout=5000)
    ready(qtbot, ctl)
    ctl.pause()
    qtbot.waitUntil(lambda: states and states[-1] is False, timeout=5000)
    assert not ctl.is_playing


def test_end_of_last_file_finishes_book(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", files=2)
    seen = []
    ctl.bookChanged.connect(seen.append)
    ctl.play_book(a)
    ready(qtbot, ctl)
    ctl.next_file()
    assert a["file_index"] == 1
    ctl.next_file()                                    # za ostatnim plikiem
    assert a["finished"] is True and a["file_index"] == 0 and a["position_ms"] == 0
    assert ctl.current is None and seen[-1] is None


def test_prev_file_restarts_when_far_in_file(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", files=2, seconds=8)
    a["file_index"] = 1
    ctl.play_book(a)
    ready(qtbot, ctl)
    qtbot.waitUntil(lambda: ctl.player.position() > 300, timeout=5000)
    ctl.player.setPosition(6500)
    qtbot.waitUntil(lambda: ctl.player.position() >= 6400, timeout=5000)
    ctl.prev_file()                                    # >5 s w pliku => początek pliku
    assert a["file_index"] == 1
    qtbot.waitUntil(lambda: ctl.player.position() < 1500, timeout=5000)


def test_duration_backfilled_when_mutagen_returned_zero(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=3)
    a["durations"] = [0]
    ctl.play_book(a)
    qtbot.waitUntil(lambda: a["durations"][0] > 2000, timeout=8000)


# ---------------------------------------------------------------- prędkość, przewijanie

def test_per_book_speed_and_global_default(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A")
    b = mkbook(library, audio_dir, "B")
    ctl.play_book(a)
    ctl.set_speed(1.5)
    assert a["speed"] == 1.5 and library.settings["speed"] == 1.5
    b["speed"] = 0.75
    assert ctl.rate_for(b) == 0.75                     # własna prędkość książki
    library.settings["per_book_speed"] = False
    assert ctl.rate_for(b) == 1.5                      # wyłączone => globalna
    c = mkbook(library, audio_dir, "C")
    assert ctl.rate_for(c) == 1.5                      # nowa książka dostaje ostatnią


def test_rewind_tiers():
    assert [rewind_for_gap(s) for s in (0, 9, 10, 59, 60, 599, 600, 1799, 1800, 99999)] == [
        0, 0, 3000, 3000, 10000, 10000, 20000, 20000, 30000, 30000]


def test_auto_rewind_applies_after_long_gap_and_can_be_disabled(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=60)
    a["position_ms"] = 45000
    a["last_played_at"] = time.time() - 4000           # >30 min temu => −30 s
    ctl.play_book(a)
    assert ctl.pending_seek == 15000
    ctl.stop(save=False)
    a["position_ms"] = 45000
    a["last_played_at"] = time.time() - 4000
    library.settings["auto_rewind"] = False
    ctl.play_book(a)
    assert ctl.pending_seek == 45000


def test_resume_after_long_pause_rewinds(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=60)
    ctl.play_book(a)
    ready(qtbot, ctl)
    ctl.player.setPosition(40000)
    qtbot.waitUntil(lambda: ctl.player.position() >= 39900, timeout=5000)
    ctl.pause()
    ctl._paused_at = time.time() - 700                 # 11+ min => −20 s
    ctl.resume()
    qtbot.waitUntil(lambda: 19000 <= ctl.player.position() <= 22500, timeout=5000)


# ---------------------------------------------------------------- usypianie

def test_sleep_timer_signals_and_cancel(qtbot, ctl, library, audio_dir):
    seen = []
    ctl.sleepChanged.connect(seen.append)
    ctl.start_sleep(minutes=15)
    assert seen[-1] == 900
    ctl.cancel_sleep()
    assert seen[-1] == -1 and not ctl._sleep_timer.isActive()
    ctl.start_sleep(end_of_file=True)
    assert seen[-1] == -2 and ctl.sleep_end_of_file


def test_sleep_expiry_fades_out_then_pauses_and_restores_volume(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=30)
    ctl.audio.setVolume(0.8)
    ctl.play_book(a)
    ready(qtbot, ctl)
    ctl.start_sleep(minutes=1)
    ctl._sleep_deadline = time.monotonic() - 1
    ctl._sleep_tick()
    assert ctl._fade_timer.isActive()
    volumes = []
    for _ in range(20):
        if not ctl._fade_timer.isActive():
            break
        ctl._fade_step()
        volumes.append(round(ctl.audio.volume(), 3))
    assert volumes and volumes[0] < 0.8
    assert volumes[:-1] == sorted(volumes[:-1], reverse=True)   # głośność tylko maleje
    assert not ctl._fade_timer.isActive()
    qtbot.waitUntil(lambda: not ctl.is_playing, timeout=5000)
    assert ctl.audio.volume() == pytest.approx(0.8)    # głośność przywrócona po wyciszeniu


def test_resume_during_fade_cancels_it_and_restores_volume(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=30)
    ctl.audio.setVolume(0.6)
    ctl.play_book(a)
    ready(qtbot, ctl)
    ctl.start_sleep(minutes=1)
    ctl._sleep_deadline = time.monotonic() - 1
    ctl._sleep_tick()
    ctl._fade_step()
    assert ctl.audio.volume() < 0.6
    ctl.resume()
    assert not ctl._fade_timer.isActive() and ctl.audio.volume() == pytest.approx(0.6)


def test_sleep_until_end_of_file_pauses_on_next_file(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", files=2, seconds=5)
    ctl.play_book(a)
    ready(qtbot, ctl)
    ctl.start_sleep(end_of_file=True)
    ctl._on_status(MS.EndOfMedia)                      # koniec pierwszego pliku
    assert a["file_index"] == 1 and not ctl.sleep_end_of_file
    qtbot.waitUntil(lambda: not ctl.is_playing, timeout=5000)


# ---------------------------------------------------------------- zakładki, statystyki

def test_bookmarks_sorted_and_persisted(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=10)
    assert ctl.add_bookmark() is None                  # nic nie gra
    ctl.play_book(a)
    ready(qtbot, ctl)
    ctl.player.setPosition(6000)
    qtbot.waitUntil(lambda: ctl.player.position() >= 5900, timeout=5000)
    late = ctl.add_bookmark()
    ctl.player.setPosition(1000)
    qtbot.waitUntil(lambda: ctl.player.position() < 3000, timeout=5000)
    early = ctl.add_bookmark("Początek")
    assert [b["id"] for b in a["bookmarks"]] == [early["id"], late["id"]]
    assert early["title"] == "Początek" and late["title"].startswith("Zakładka ")
    assert lib.Library(library.app_dir).books[0]["bookmarks"][0]["title"] == "Początek"


def test_listening_time_is_recorded_while_playing(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=10)
    ctl.play_book(a)
    qtbot.waitUntil(lambda: a["listened_ms"] > 600, timeout=8000)
    assert library.settings["stats"]["total_ms"] >= a["listened_ms"] - 5
    before = a["listened_ms"]
    ctl.pause()
    qtbot.wait(700)
    assert a["listened_ms"] - before < 300             # pauza nie nalicza czasu


# ---------------------------------------------------------------- rozdziały (jump_to)

def test_jump_within_same_file_seeks_without_reload(qtbot, ctl, library, audio_dir):
    a = mkbook(library, audio_dir, "A", seconds=10)
    ctl.play_book(a)
    ready(qtbot, ctl)
    loads = []
    ctl.fileChanged.connect(lambda: loads.append(1))
    assert ctl.jump_to(a, 0, 7000)
    qtbot.waitUntil(lambda: ctl.player.position() >= 6900, timeout=5000)
    assert loads == []                                 # bez ponownego ładowania pliku


def test_player_ctl_module_has_no_widget_imports():
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "player_ctl.py"),
               encoding="utf-8").read()
    assert "QtWidgets" not in src                      # sterownik testowalny bez GUI
