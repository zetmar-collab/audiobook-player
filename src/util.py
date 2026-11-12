"""Drobne funkcje pomocnicze bez zależności od Qt."""


def fmt_ms(ms):
    """Czas w formacie m:ss albo h:mm:ss."""
    s = max(0, int(ms // 1000))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
