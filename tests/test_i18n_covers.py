"""Tłumaczenia (parytet PL/EN, klucze z kodu) oraz obsługa obrazów okładek."""
import glob
import os
import re
import string

import i18n

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def _placeholders(text):
    return sorted(f for _, f, _, _ in string.Formatter().parse(text) if f)


def test_every_key_has_both_languages_with_same_placeholders():
    pl, en = i18n.STRINGS["pl"], i18n.STRINGS["en"]
    assert set(pl) == set(en)
    for key in pl:
        assert pl[key].strip() and en[key].strip(), key
        assert _placeholders(pl[key]) == _placeholders(en[key]), f"inne znaczniki w {key}"


def test_all_keys_used_in_code_exist():
    used = set()
    for path in glob.glob(os.path.join(SRC, "*.py")):
        if path.endswith("i18n.py"):
            continue
        text = open(path, encoding="utf-8").read()
        used |= set(re.findall(r'\btr\(\s*"([a-z0-9_]+)"', text))
        # klucze podawane parami (klucz, dane) do list rozwijanych
        used |= set(re.findall(r'\(\s*"((?:sort|filter)_[a-z_]+)"\s*,\s*"', text))
    missing = sorted(k for k in used if k not in i18n.STRINGS["pl"])
    assert not missing, f"brak tłumaczeń: {missing}"
    for code in ("rate_limit", "http", "timeout", "offline", "bad_response", "error"):
        assert f"err_{code}" in i18n.STRINGS["pl"]
    for key in ("theme_light", "theme_dark", "theme_system"):
        assert key in i18n.STRINGS["en"]


def test_tr_formats_switches_language_and_falls_back():
    assert i18n.tr("added_book", title="X") == "Dodano: X"
    i18n.set_language("en")
    assert i18n.tr("added_book", title="X") == "Added: X"
    assert i18n.tr("nie_ma_takiego_klucza") == "nie_ma_takiego_klucza"
    i18n.set_language("xx")
    assert i18n.language() == "pl"


def test_polish_plurals():
    assert [i18n.plural_files(n) for n in (1, 2, 5, 12, 22, 112)] == [
        "1 plik", "2 pliki", "5 plików", "12 plików", "22 pliki", "112 plików"]
    i18n.set_language("en")
    assert (i18n.plural_files(1), i18n.plural_files(3)) == ("1 file", "3 files")


def test_detect_system_language_is_pl_or_en():
    assert i18n.detect_system_language() in ("pl", "en")


def test_no_deprecated_locale_call():
    assert "getdefaultlocale" not in open(os.path.join(SRC, "i18n.py"), encoding="utf-8").read()


# ---------------------------------------------------------------- okładki (Qt)

def _jpeg_bytes(w=40, h=60, color="#336699"):
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    from PyQt6.QtGui import QColor, QImage
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    data = QByteArray()                 # musi żyć tak długo jak bufor
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "JPG")
    buf.close()
    return bytes(data)


def test_save_cover_bytes_normalizes_large_images(qapp, tmp_path):
    from PyQt6.QtGui import QImage
    import covers
    dest = str(tmp_path / "c.jpg")
    assert covers.save_cover_bytes(_jpeg_bytes(3000, 2000), dest)
    img = QImage(dest)
    assert max(img.width(), img.height()) <= covers.MAX_COVER_SIDE
    assert abs(img.width() / img.height() - 1.5) < 0.02           # zachowane proporcje


def test_save_cover_rejects_non_images(qapp, tmp_path):
    import covers
    dest = str(tmp_path / "c.jpg")
    assert covers.save_cover_bytes(b"<html>to nie obraz</html>", dest) is False
    assert not os.path.exists(dest)
    assert covers.save_cover_file(str(tmp_path / "brak.png"), dest) is False


def test_transparent_png_is_flattened_on_white_not_black(qapp, tmp_path):
    from PyQt6.QtGui import QColor, QImage
    import covers
    src = QImage(20, 20, QImage.Format.Format_ARGB32)
    src.fill(QColor(0, 0, 0, 0))
    p = str(tmp_path / "t.png")
    src.save(p, "PNG")
    dest = str(tmp_path / "t.jpg")
    assert covers.save_cover_file(p, dest)
    px = QImage(dest).pixelColor(10, 10)
    assert px.red() > 240 and px.green() > 240 and px.blue() > 240


def test_scaled_pixmap_cache_and_invalidation_on_change(qapp, tmp_path):
    import covers
    path = str(tmp_path / "k.jpg")
    covers.save_cover_bytes(_jpeg_bytes(200, 300, "#ff0000"), path)
    a = covers.scaled_pixmap(path, 56, 56)
    assert a is not None and max(a.width(), a.height()) == 56
    assert covers.scaled_pixmap(str(tmp_path / "brak.jpg"), 56, 56) is None
    assert covers.scaled_pixmap("", 56, 56) is None
    before = a.toImage().pixelColor(a.width() // 2, a.height() // 2).red()
    covers.save_cover_bytes(_jpeg_bytes(200, 300, "#0000ff"), path)
    os.utime(path, (os.path.getatime(path), os.path.getmtime(path) + 5))
    b = covers.scaled_pixmap(path, 56, 56)
    assert b.toImage().pixelColor(b.width() // 2, b.height() // 2).red() != before


def test_cover_saver_for_uses_book_id(qapp, tmp_path):
    import covers
    save = covers.cover_saver_for(str(tmp_path))
    out = save(_jpeg_bytes(), "abc")
    assert out == os.path.join(str(tmp_path), "abc.jpg") and os.path.getsize(out) > 0
    assert save(b"junk", "x") == ""
