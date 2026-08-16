"""Tłumaczenia interfejsu (PL/EN).

Użycie: `from i18n import tr`, potem `tr("add_folder")`.
Zmiana języka: `set_language("en")` — okno główne przebudowuje wtedy UI.
"""

LANGUAGES = [("pl", "Polski"), ("en", "English")]
_current = "pl"

STRINGS = {
    "pl": {
        # --- okno, paski
        "app_title": "Odtwarzacz audiobooków",
        "toolbar_main": "Główny",
        "ready": "Gotowy",
        # --- pasek narzędzi
        "add_folder": "Dodaj katalog",
        "add_many": "Dodaj wiele katalogów",
        "add_file": "Dodaj plik",
        "clear_library": "Wyczyść bibliotekę",
        "sort": " Sortuj: ",
        "sort_recent": "Ostatnio słuchane",
        "sort_title": "Tytuł",
        "sort_author": "Autor",
        "sort_added": "Ostatnio dodane",
        "search_placeholder": "Szukaj w bibliotece…",
        # --- menu
        "menu_settings": "&Ustawienia",
        "menu_language": "Język",
        "menu_theme": "Motyw",
        "theme_light": "Jasny",
        "theme_dark": "Ciemny",
        "theme_system": "Jak w systemie",
        "menu_help": "&Pomoc",
        "menu_about": "O programie",
        # --- panel szczegółów
        "files_chapters": "Pliki / rozdziały:",
        "no_author": "—",
        # --- odtwarzacz
        "nothing_playing": "Nic nie odtwarzam",
        "prev_file": "Poprzedni plik",
        "next_file": "Następny plik",
        "back_30": "Cofnij 30 s",
        "back_10": "Cofnij 10 s",
        "fwd_10": "Do przodu 10 s",
        "fwd_30": "Do przodu 30 s",
        "play_pause": "Odtwórz / pauza",
        "speed": "Prędkość:",
        "sleep_btn": "⏰ Usypianie",
        "sleep_tooltip": "Zatrzymaj odtwarzanie po zadanym czasie",
        "sleep_title": "Wyłącznik czasowy",
        "sleep_prompt": "Zatrzymaj odtwarzanie po:",
        "sleep_off": "Wyłącz",
        "sleep_minutes": "{n} minut",
        "sleep_short": "⏰ {n} min",
        "sleep_will_stop": "Odtwarzanie zatrzyma się za {n} min",
        "sleep_stopped": "Wyłącznik czasowy: odtwarzanie zatrzymane",
        # --- dialogi plików
        "dlg_choose_folder": "Wybierz katalog z audiobookiem",
        "dlg_choose_parent": "Wybierz katalog nadrzędny — każdy podkatalog stanie się audiobookiem",
        "dlg_choose_files": "Wybierz plik(i) audio",
        "audio_files": "Pliki audio",
        # --- komunikaty
        "added_book": "Dodano: {title}",
        "added_books": "Dodano {n} audiobooków",
        "added_files": "Dodano {n} plików",
        "info_folder_exists": "Katalog już jest w bibliotece albo nie zawiera plików audio.",
        "info_no_new": "Nie znaleziono nowych audiobooków w podkatalogach.",
        "clear_title": "Wyczyść bibliotekę",
        "clear_question": "Usunąć wszystkie pozycje z biblioteki ({n})?\n"
                          "Pliki audio na dysku NIE zostaną skasowane.",
        "remove_title": "Usuń audiobook",
        "remove_question": "Usunąć „{title}” z biblioteki?\n"
                           "Pliki audio na dysku NIE zostaną skasowane.",
        "missing_file": "Brak pliku: {path}",
        "play_error": "Błąd odtwarzania: {err}",
        "finished_msg": "Ukończono: {title} 🎉",
        "meta_updated": "Metadane zaktualizowane",
        # --- menu kontekstowe
        "ctx_play": "▶ Odtwórz (wznów)",
        "ctx_play_start": "Odtwórz od początku",
        "ctx_metadata": "Pobierz metadane z internetu…",
        "ctx_edit": "Edytuj tytuł/autora…",
        "ctx_mark_done": "Oznacz jako ukończony",
        "ctx_mark_undone": "Oznacz jako nieukończony",
        "ctx_reset": "Wyzeruj postęp",
        "ctx_open_location": "Otwórz lokalizację na dysku",
        "ctx_remove": "Usuń z biblioteki",
        "edit_title": "Tytuł",
        "edit_title_label": "Tytuł:",
        "edit_author": "Autor",
        "edit_author_label": "Autor:",
        # --- dialog metadanych
        "meta_dialog_title": "Metadane — {title}",
        "meta_search": "Szukaj",
        "meta_searching": "Szukam…",
        "meta_found": "Znaleziono wyników: {n}",
        "meta_none": "Brak wyników — zmień zapytanie.",
        "meta_apply": "Zastosuj",
        "meta_cancel": "Anuluj",
        "meta_fetching": "Pobieram szczegóły…",
        "meta_source": "Źródło",
        # --- element listy
        "n_files": "{n} plików",
        "badge_finished": "✔ ukończony",
        "file_x_of_y": "  ·  plik {i}/{n}",
        # --- o programie
        "about_title": "O programie",
        "about_text": "<b>Odtwarzacz audiobooków {version}</b><br><br>"
                      "Odtwarzacz audiobooków z biblioteką, zapamiętywaniem pozycji "
                      "i pobieraniem metadanych z serwisów polskich i zagranicznych.<br><br>"
                      "Autor: Marek Zettel<br>"
                      "Licencja: GPL-3.0<br>"
                      '<a href="https://github.com/zetmar-collab/audiobook-player">'
                      "github.com/zetmar-collab/audiobook-player</a>",
    },
    "en": {
        "app_title": "Audiobook Player",
        "toolbar_main": "Main",
        "ready": "Ready",
        "add_folder": "Add folder",
        "add_many": "Add multiple folders",
        "add_file": "Add file",
        "clear_library": "Clear library",
        "sort": " Sort: ",
        "sort_recent": "Recently played",
        "sort_title": "Title",
        "sort_author": "Author",
        "sort_added": "Recently added",
        "search_placeholder": "Search the library…",
        "menu_settings": "&Settings",
        "menu_language": "Language",
        "menu_theme": "Theme",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "theme_system": "Follow system",
        "menu_help": "&Help",
        "menu_about": "About",
        "files_chapters": "Files / chapters:",
        "no_author": "—",
        "nothing_playing": "Nothing playing",
        "prev_file": "Previous file",
        "next_file": "Next file",
        "back_30": "Back 30 s",
        "back_10": "Back 10 s",
        "fwd_10": "Forward 10 s",
        "fwd_30": "Forward 30 s",
        "play_pause": "Play / pause",
        "speed": "Speed:",
        "sleep_btn": "⏰ Sleep timer",
        "sleep_tooltip": "Stop playback after a set time",
        "sleep_title": "Sleep timer",
        "sleep_prompt": "Stop playback after:",
        "sleep_off": "Off",
        "sleep_minutes": "{n} minutes",
        "sleep_short": "⏰ {n} min",
        "sleep_will_stop": "Playback will stop in {n} min",
        "sleep_stopped": "Sleep timer: playback stopped",
        "dlg_choose_folder": "Choose an audiobook folder",
        "dlg_choose_parent": "Choose a parent folder — each subfolder becomes an audiobook",
        "dlg_choose_files": "Choose audio file(s)",
        "audio_files": "Audio files",
        "added_book": "Added: {title}",
        "added_books": "Added {n} audiobooks",
        "added_files": "Added {n} files",
        "info_folder_exists": "This folder is already in the library or contains no audio files.",
        "info_no_new": "No new audiobooks found in the subfolders.",
        "clear_title": "Clear library",
        "clear_question": "Remove all items from the library ({n})?\n"
                          "Audio files on disk will NOT be deleted.",
        "remove_title": "Remove audiobook",
        "remove_question": "Remove “{title}” from the library?\n"
                           "Audio files on disk will NOT be deleted.",
        "missing_file": "File not found: {path}",
        "play_error": "Playback error: {err}",
        "finished_msg": "Finished: {title} 🎉",
        "meta_updated": "Metadata updated",
        "ctx_play": "▶ Play (resume)",
        "ctx_play_start": "Play from the beginning",
        "ctx_metadata": "Fetch metadata from the internet…",
        "ctx_edit": "Edit title/author…",
        "ctx_mark_done": "Mark as finished",
        "ctx_mark_undone": "Mark as unfinished",
        "ctx_reset": "Reset progress",
        "ctx_open_location": "Open location on disk",
        "ctx_remove": "Remove from library",
        "edit_title": "Title",
        "edit_title_label": "Title:",
        "edit_author": "Author",
        "edit_author_label": "Author:",
        "meta_dialog_title": "Metadata — {title}",
        "meta_search": "Search",
        "meta_searching": "Searching…",
        "meta_found": "Results found: {n}",
        "meta_none": "No results — try a different query.",
        "meta_apply": "Apply",
        "meta_cancel": "Cancel",
        "meta_fetching": "Fetching details…",
        "meta_source": "Source",
        "n_files": "{n} files",
        "badge_finished": "✔ finished",
        "file_x_of_y": "  ·  file {i}/{n}",
        "about_title": "About",
        "about_text": "<b>Audiobook Player {version}</b><br><br>"
                      "An audiobook player with a library, playback position memory "
                      "and metadata lookup from Polish and international sources.<br><br>"
                      "Author: Marek Zettel<br>"
                      "License: GPL-3.0<br>"
                      '<a href="https://github.com/zetmar-collab/audiobook-player">'
                      "github.com/zetmar-collab/audiobook-player</a>",
    },
}


def set_language(lang):
    global _current
    _current = lang if lang in STRINGS else "pl"


def language():
    return _current


def detect_system_language():
    """Zwraca 'pl' dla polskiego ustawienia systemu, inaczej 'en'."""
    import locale
    try:
        code = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        code = ""
    return "pl" if code.startswith("pl") else "en"


def tr(key, **kwargs):
    text = STRINGS.get(_current, STRINGS["pl"]).get(key) or STRINGS["pl"].get(key, key)
    return text.format(**kwargs) if kwargs else text


def plural_files(n):
    """Poprawna odmiana: 1 plik / 2 pliki / 5 plików (PL), 1 file / 2 files (EN)."""
    if _current != "pl":
        return f"{n} file" if n == 1 else f"{n} files"
    if n == 1:
        return "1 plik"
    last, last2 = n % 10, n % 100
    if 2 <= last <= 4 and not 12 <= last2 <= 14:
        return f"{n} pliki"
    return f"{n} plików"
