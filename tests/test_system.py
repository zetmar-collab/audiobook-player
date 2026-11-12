"""Obsługa wyjątków (B2), jedna instancja (B10), klawisze multimedialne, start aplikacji."""
import json
import os
import subprocess
import sys
import textwrap
import time
import uuid

import pytest
from PyQt6.QtNetwork import QLocalSocket

import applog
from singleinstance import SingleInstance

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")


def run_python(code, appdata, timeout=60):
    env = dict(os.environ, APPDATA=str(appdata), QT_QPA_PLATFORM="offscreen",
               PYTHONIOENCODING="utf-8", XDG_DATA_HOME=str(appdata))
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env=env, timeout=timeout, cwd=SRC)


# ---------------------------------------------------------------- B2

@pytest.fixture
def clean_applog(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(applog, "_last_notified", 0.0)
    monkeypatch.setattr(applog, "_in_hook", False)
    applog.set_notifier(None)
    yield
    for h in list(applog.log.handlers):
        h.close()
        applog.log.removeHandler(h)
    applog.set_notifier(None)


def test_excepthook_logs_traceback_and_notifies(tmp_path, clean_applog):
    log_file = tmp_path / "logs" / "error.log"
    applog.setup_logging(str(log_file))
    seen = []
    applog.set_notifier(seen.append)
    try:
        {}["brak_klucza"]
    except KeyError:
        applog._handle(*sys.exc_info())
    text = log_file.read_text(encoding="utf-8")
    assert "Nieobsłużony wyjątek" in text and "KeyError" in text and "brak_klucza" in text
    assert seen == ["KeyError: 'brak_klucza'"]


def test_notifications_are_rate_limited_and_never_raise(tmp_path, clean_applog):
    applog.setup_logging(str(tmp_path / "e.log"))
    calls = []
    applog.set_notifier(lambda t: calls.append(t))
    for _ in range(5):
        applog._handle(ValueError, ValueError("x"), None)
    assert len(calls) == 1                              # nie zalewamy użytkownika okienkami

    def boom(_t):
        raise RuntimeError("awaria w samym powiadomieniu")
    monkey_last = 0.0
    applog._last_notified = monkey_last
    applog.set_notifier(boom)
    applog._handle(ValueError, ValueError("y"), None)   # nie może rzucić wyjątku


def test_install_excepthook_replaces_sys_excepthook(clean_applog):
    applog.install_excepthook()
    assert sys.excepthook is applog._handle


def test_unhandled_exception_in_qt_slot_no_longer_kills_process(tmp_path):
    """Dowód dla B2: bez hooka proces ginie (0xC0000409), z hookiem działa dalej."""
    body = textwrap.dedent(f"""
        import sys, os
        sys.path.insert(0, r"{SRC}")
        import applog
        applog.setup_logging(r"{tmp_path / 'e.log'}")
        {{install}}
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])
        QTimer.singleShot(50, lambda: {{}}['brak_klucza'])
        QTimer.singleShot(600, lambda: print('ZYJE', flush=True))
        QTimer.singleShot(900, app.quit)
        app.exec()
        print('KONIEC', flush=True)
    """)
    survived = run_python(body.replace("{install}", "applog.install_excepthook()"), tmp_path)
    assert "ZYJE" in survived.stdout and "KONIEC" in survived.stdout and survived.returncode == 0
    assert "brak_klucza" in (tmp_path / "e.log").read_text(encoding="utf-8")
    killed = run_python(body.replace("{install}", ""), tmp_path)
    assert "ZYJE" not in killed.stdout and killed.returncode != 0       # stare zachowanie


# ---------------------------------------------------------------- B10: jedna instancja

@pytest.fixture
def key():
    return f"AudiobookPlayer-test-{uuid.uuid4().hex[:8]}"


def test_second_instance_forwards_paths_to_first(qtbot, key):
    first = SingleInstance(key)
    assert first.listen()
    second = SingleInstance(key)
    with qtbot.waitSignal(first.messageReceived, timeout=5000) as sig:
        assert second.send_to_running(["C:/a/b.m4b", "D:/c"]) is True
    assert sig.args == [["C:/a/b.m4b", "D:/c"]]


def test_no_running_instance_means_we_become_primary(qtbot, key):
    inst = SingleInstance(key)
    assert inst.send_to_running(["x"], timeout=200) is False
    assert inst.listen()


def test_empty_message_means_just_raise_window(qtbot, key):
    first = SingleInstance(key)
    first.listen()
    with qtbot.waitSignal(first.messageReceived, timeout=5000) as sig:
        assert SingleInstance(key).send_to_running([]) is True
    assert sig.args == [[]]


def test_garbage_message_is_survived(qtbot, key):
    first = SingleInstance(key)
    first.listen()
    sock = QLocalSocket()
    sock.connectToServer(first.name)
    assert sock.waitForConnected(1000)
    with qtbot.waitSignal(first.messageReceived, timeout=5000) as sig:
        sock.write(b"to nie jest json \xff\xfe")
        sock.flush()
        sock.waitForBytesWritten(1000)
        sock.disconnectFromServer()
    assert sig.args == [[]]


# ---------------------------------------------------------------- klawisze multimedialne

@pytest.mark.skipif(sys.platform != "win32", reason="RegisterHotKey tylko na Windows")
def test_media_keys_dispatch_and_unregister(qtbot):
    import ctypes
    import winmedia
    hits = []
    keys = winmedia.MediaKeys({"play_pause": lambda: hits.append("pp"),
                               "next": lambda: hits.append("next"),
                               "prev": lambda: hits.append("prev"),
                               "stop": lambda: hits.append("stop")})
    count = keys.enable()
    try:
        if count == 0:
            pytest.skip("klawisze multimedialne zajęte przez inną aplikację")
        tid = ctypes.windll.kernel32.GetCurrentThreadId()
        post = ctypes.windll.user32.PostThreadMessageW
        post(tid, winmedia.WM_HOTKEY, 1, 0)
        post(tid, winmedia.WM_HOTKEY, 2, 0)
        post(tid, winmedia.WM_HOTKEY, 999, 0)           # nieznany identyfikator — ignorowany
        qtbot.waitUntil(lambda: len(hits) >= 2, timeout=3000)
        assert hits[:2] == ["pp", "next"] and "stop" not in hits
    finally:
        keys.disable()
    assert keys.registered == set() and keys.active is False
    keys.disable()                                      # ponowne wyłączenie jest bezpieczne


def test_media_keys_enable_is_noop_off_windows(monkeypatch):
    import winmedia
    monkeypatch.setattr(winmedia, "IS_WINDOWS", False)
    keys = winmedia.MediaKeys({})
    assert keys.enable() == 0
    keys.disable()


# ---------------------------------------------------------------- start aplikacji

def test_application_starts_runs_and_exits_cleanly(tmp_path):
    env = dict(os.environ, APPDATA=str(tmp_path), XDG_DATA_HOME=str(tmp_path),
               QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    t0 = time.time()
    done = subprocess.run([sys.executable, os.path.join(SRC, "main.py"), "--smoke-test"],
                          capture_output=True, text=True, env=env, timeout=60, cwd=SRC)
    assert done.returncode == 0, done.stderr[-800:]
    assert time.time() - t0 < 30
    assert "Traceback" not in done.stderr


def test_application_starts_with_file_argument_and_adds_it(tmp_path):
    from conftest import make_wav
    book_dir = tmp_path / "audio" / "Z argumentu"
    make_wav(book_dir / "01.wav")
    env = dict(os.environ, APPDATA=str(tmp_path / "data"), XDG_DATA_HOME=str(tmp_path / "data"),
               QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable, os.path.join(SRC, "main.py"), "--smoke-test",
                           str(book_dir)], capture_output=True, text=True, env=env, timeout=60, cwd=SRC)
    assert done.returncode == 0, done.stderr[-800:]
    lib_file = tmp_path / "data" / "AudiobookPlayer" / "library.json"
    data = json.loads(lib_file.read_text(encoding="utf-8"))
    assert [b["title"] for b in data["books"]] == ["Z argumentu"]
