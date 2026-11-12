"""Tłumaczenia interfejsu (PL/EN).

Użycie: `from i18n import tr`, potem `tr("add_folder")`.
Zmiana języka: `set_language("en")` — okno główne przebudowuje wtedy UI.

Każdy klucz to para (polski, angielski) w jednym wpisie, więc nie da się dodać
tłumaczenia tylko w jednym języku. Zgodność kluczy użytych w kodzie ze słownikiem
oraz identyczne znaczniki `{...}` w obu językach pilnuje `tests/test_i18n.py`.
"""

LANGUAGES = [("pl", "Polski"), ("en", "English")]
_current = "pl"

_T = {
    # --- okno, paski
    "app_title": ("Odtwarzacz audiobooków", "Audiobook Player"),
    "toolbar_main": ("Główny", "Main"),
    "ready": ("Gotowy", "Ready"),
    "ok": ("OK", "OK"),
    "cancel": ("Anuluj", "Cancel"),
    "close": ("Zamknij", "Close"),
    "yes": ("Tak", "Yes"),
    "no": ("Nie", "No"),

    # --- pasek narzędzi i lista
    "add_folder": ("Dodaj katalog", "Add folder"),
    "add_many": ("Dodaj wiele katalogów", "Add multiple folders"),
    "add_file": ("Dodaj plik", "Add file"),
    "clear_library": ("Wyczyść bibliotekę", "Clear library"),
    "sort": (" Sortuj: ", " Sort: "),
    "sort_recent": ("Ostatnio słuchane", "Recently played"),
    "sort_title": ("Tytuł", "Title"),
    "sort_author": ("Autor", "Author"),
    "sort_added": ("Ostatnio dodane", "Recently added"),
    "filter": (" Pokaż: ", " Show: "),
    "filter_all": ("Wszystkie", "All"),
    "filter_in_progress": ("W trakcie", "In progress"),
    "filter_unplayed": ("Nieodsłuchane", "Unplayed"),
    "filter_finished": ("Ukończone", "Finished"),
    "search_placeholder": ("Szukaj w bibliotece…", "Search the library…"),

    # --- menu
    "menu_library": ("&Biblioteka", "&Library"),
    "menu_playback": ("&Odtwarzanie", "&Playback"),
    "menu_settings": ("&Ustawienia", "&Settings"),
    "menu_language": ("Język", "Language"),
    "menu_theme": ("Motyw", "Theme"),
    "theme_light": ("Jasny", "Light"),
    "theme_dark": ("Ciemny", "Dark"),
    "theme_system": ("Jak w systemie", "Follow system"),
    "menu_help": ("&Pomoc", "&Help"),
    "menu_about": ("O programie", "About"),
    "menu_shortcuts": ("Skróty klawiszowe", "Keyboard shortcuts"),
    "menu_licenses": ("Licencje i uznania", "Licenses and credits"),
    "open_data_folder": ("Otwórz folder danych", "Open data folder"),
    "open_logs": ("Otwórz folder z logiem błędów", "Open error log folder"),
    "opt_auto_rewind": ("Cofaj kilka sekund po dłuższej przerwie",
                        "Rewind a few seconds after a long pause"),
    "opt_per_book_speed": ("Zapamiętuj prędkość dla każdej książki",
                           "Remember playback speed per book"),
    "opt_media_keys": ("Globalne klawisze multimedialne", "Global media keys"),
    "opt_group_authors": ("Grupuj po autorze", "Group by author"),
    "opt_google_key": ("Klucz API Google Books…", "Google Books API key…"),
    "google_key_prompt": (
        "Klucz API Google Books (opcjonalny, zwiększa limit zapytań). Puste pole wyłącza klucz:",
        "Google Books API key (optional, raises the request limit). Leave empty to disable:"),

    # --- panel szczegółów
    "files_chapters": ("Pliki / rozdziały:", "Files / chapters:"),
    "no_author": ("—", "—"),

    # --- odtwarzacz
    "nothing_playing": ("Nic nie odtwarzam", "Nothing playing"),
    "prev_chapter": ("Poprzedni rozdział / plik", "Previous chapter / file"),
    "next_chapter": ("Następny rozdział / plik", "Next chapter / file"),
    "back_30": ("Cofnij 30 s", "Back 30 s"),
    "back_10": ("Cofnij 10 s", "Back 10 s"),
    "fwd_10": ("Do przodu 10 s", "Forward 10 s"),
    "fwd_30": ("Do przodu 30 s", "Forward 30 s"),
    "play_pause": ("Odtwórz / pauza", "Play / pause"),
    "speed": ("Prędkość:", "Speed:"),
    "volume": ("Głośność", "Volume"),
    "volume_up": ("Głośniej", "Volume up"),
    "volume_down": ("Ciszej", "Volume down"),
    "book_time": ("Książka: {elapsed} / {total} · pozostało {remaining}",
                  "Book: {elapsed} / {total} · {remaining} left"),
    "book_time_eta": ("(≈ {eta} przy tej prędkości)", "(≈ {eta} at this speed)"),
    "sleep_btn": ("⏰ Usypianie", "⏰ Sleep timer"),
    "sleep_tooltip": ("Zatrzymaj odtwarzanie po zadanym czasie", "Stop playback after a set time"),
    "sleep_off": ("Wyłącz", "Off"),
    "sleep_minutes": ("{n} minut", "{n} minutes"),
    "sleep_end_of_file": ("Do końca pliku / rozdziału", "Until the end of this file"),
    "sleep_eof_short": ("⏰ do końca pliku", "⏰ end of file"),
    "sleep_stopped": ("Wyłącznik czasowy: odtwarzanie zatrzymane", "Sleep timer: playback stopped"),
    "err_no_files": (
        "Nie znaleziono plików audio książki „{title}”. Sprawdź, czy dysk jest podłączony.",
        "Couldn't find the audio files of “{title}”. Check that the drive is connected."),
    "skipped_missing": ("Pominięto brakujące pliki: {n}", "Skipped missing files: {n}"),
    "play_error": ("Błąd odtwarzania: {err}", "Playback error: {err}"),
    "finished_msg": ("Ukończono: {title} 🎉", "Finished: {title} 🎉"),
    "save_failed": ("Nie udało się zapisać biblioteki: {err}", "Couldn't save the library: {err}"),

    # --- zakładki
    "bookmark_add": ("Dodaj zakładkę", "Add bookmark"),
    "bookmark_added": ("Dodano zakładkę: {title}", "Bookmark added: {title}"),
    "bookmark_default": ("Zakładka {time}", "Bookmark {time}"),
    "bookmarks_open": ("Zakładki…", "Bookmarks…"),
    "bookmarks_title": ("Zakładki — {title}", "Bookmarks — {title}"),
    "bookmarks_empty": ("Brak zakładek. Dodaj je w trakcie słuchania (Ctrl+B).",
                        "No bookmarks yet. Add one while listening (Ctrl+B)."),
    "bookmark_go": ("Przejdź", "Go to"),
    "bookmark_rename": ("Zmień nazwę", "Rename"),
    "bookmark_delete": ("Usuń", "Delete"),
    "bookmark_name": ("Nazwa zakładki:", "Bookmark name:"),
    "bookmark_need_playing": ("Zakładkę można dodać podczas odtwarzania książki.",
                              "You can add a bookmark while a book is playing."),
    "bookmark_need_book": ("Najpierw wybierz książkę.", "Select a book first."),

    # --- dodawanie
    "dlg_choose_folder": ("Wybierz katalog z audiobookiem", "Choose an audiobook folder"),
    "dlg_choose_parent": ("Wybierz katalog nadrzędny — każdy podkatalog stanie się audiobookiem",
                          "Choose a parent folder — each subfolder becomes an audiobook"),
    "dlg_choose_files": ("Wybierz plik(i) audio", "Choose audio file(s)"),
    "audio_files": ("Pliki audio", "Audio files"),
    "scanning": ("Wczytuję pliki audio…", "Reading audio files…"),
    "scanning_item": ("Wczytuję ({i}/{n}): {name}", "Reading ({i}/{n}): {name}"),
    "scan_busy": ("Trwa dodawanie — poczekaj na zakończenie.",
                  "Adding is in progress — please wait for it to finish."),
    "added_book": ("Dodano: {title}", "Added: {title}"),
    "added_books": ("Dodano {n} audiobooków", "Added {n} audiobooks"),
    "info_no_new": ("Nie znaleziono nowych audiobooków do dodania.",
                    "No new audiobooks found to add."),

    # --- usuwanie
    "clear_title": ("Wyczyść bibliotekę", "Clear library"),
    "clear_question": ("Usunąć wszystkie pozycje z biblioteki ({n})?\n"
                       "Pliki audio na dysku NIE zostaną skasowane.",
                       "Remove all items from the library ({n})?\n"
                       "Audio files on disk will NOT be deleted."),
    "remove_title": ("Usuń audiobook", "Remove audiobook"),
    "remove_question": ("Usunąć „{title}” z biblioteki?\nPliki audio na dysku NIE zostaną skasowane.",
                        "Remove “{title}” from the library?\nAudio files on disk will NOT be deleted."),

    # --- menu kontekstowe
    "ctx_play": ("▶ Odtwórz (wznów)", "▶ Play (resume)"),
    "ctx_play_start": ("Odtwórz od początku", "Play from the beginning"),
    "ctx_metadata": ("Pobierz metadane z internetu…", "Fetch metadata from the internet…"),
    "ctx_cover": ("Pobierz okładkę…", "Fetch cover…"),
    "ctx_edit": ("Edytuj tytuł/autora…", "Edit title/author…"),
    "ctx_bookmarks": ("Zakładki…", "Bookmarks…"),
    "ctx_mark_done": ("Oznacz jako ukończony", "Mark as finished"),
    "ctx_mark_undone": ("Oznacz jako nieukończony", "Mark as unfinished"),
    "ctx_reset": ("Wyzeruj postęp", "Reset progress"),
    "ctx_open_location": ("Otwórz lokalizację na dysku", "Open location on disk"),
    "ctx_remove": ("Usuń z biblioteki", "Remove from library"),
    "edit_title": ("Tytuł", "Title"),
    "edit_title_label": ("Tytuł:", "Title:"),
    "edit_author": ("Autor", "Author"),
    "edit_author_label": ("Autor:", "Author:"),

    # --- dialog metadanych
    "meta_dialog_title": ("Metadane — {title}", "Metadata — {title}"),
    "meta_search": ("Szukaj", "Search"),
    "meta_searching": ("Szukam…", "Searching…"),
    "meta_found": ("Znaleziono wyników: {n}", "Results found: {n}"),
    "meta_none": ("Brak wyników — zmień zapytanie.", "No results — try a different query."),
    "meta_unavailable": ("niedostępne: {sources}", "unavailable: {sources}"),
    "meta_failed": ("Nie udało się pobrać wyników. Niedostępne: {sources}",
                    "Couldn't get any results. Unavailable: {sources}"),
    "meta_apply": ("Zastosuj", "Apply"),
    "meta_cancel": ("Anuluj", "Cancel"),
    "meta_fetching": ("Pobieram szczegóły…", "Fetching details…"),
    "meta_source": ("Źródło", "Source"),
    "meta_updated": ("Metadane zaktualizowane", "Metadata updated"),
    "err_all_sources": ("wszystkie serwisy", "all services"),
    "err_rate_limit": ("limit zapytań", "rate limit"),
    "err_http": ("błąd HTTP {detail}", "HTTP error {detail}"),
    "err_timeout": ("przekroczono czas", "timed out"),
    "err_offline": ("brak połączenia", "no connection"),
    "err_bad_response": ("nieoczekiwana odpowiedź", "unexpected response"),
    "err_error": ("błąd: {detail}", "error: {detail}"),

    # --- dialog okładki
    "cover_dialog_title": ("Okładka — {title}", "Cover — {title}"),
    "cover_found": ("Znaleziono okładek: {n}", "Covers found: {n}"),
    "cover_none": ("Brak okładek — zmień zapytanie.", "No covers found — try a different query."),
    "cover_apply": ("Ustaw okładkę", "Set cover"),
    "cover_from_file": ("Wybierz plik z dysku…", "Choose file from disk…"),
    "cover_dlg_choose_file": ("Wybierz obraz okładki", "Choose a cover image"),
    "cover_image_files": ("Obrazy", "Images"),
    "cover_download_failed": ("Nie udało się pobrać tej okładki — spróbuj innej.",
                              "Couldn't download this cover — try another one."),
    "cover_file_failed": ("Nie udało się wczytać wybranego pliku jako obrazu.",
                          "Couldn't load the selected file as an image."),
    "cover_updated": ("Okładka zaktualizowana", "Cover updated"),
    "cover_downloading": ("Pobieram okładkę…", "Downloading cover…"),

    # --- wsadowe uzupełnianie metadanych
    "batch_menu": ("Uzupełnij metadane brakujących książek…", "Fill in missing metadata…"),
    "batch_title": ("Wsadowe uzupełnianie metadanych", "Batch metadata update"),
    "batch_nothing": ("Wszystkie książki mają już okładkę i opis.",
                      "All books already have a cover and description."),
    "batch_confirm": ("Wyszukać metadane dla {n} książek bez okładki lub opisu?\n"
                      "Propozycje zatwierdzisz przed zapisaniem.",
                      "Search metadata for {n} books missing a cover or description?\n"
                      "You will review the proposals before anything is saved."),
    "batch_searching": ("Szukam ({i}/{n}): {title}", "Searching ({i}/{n}): {title}"),
    "batch_done": ("Znaleziono propozycje: {n}. Zaznacz te, które mają zostać zastosowane.",
                   "Proposals found: {n}. Tick the ones you want to apply."),
    "batch_none": ("Nie znaleziono pewnych dopasowań.", "No confident matches found."),
    "batch_apply": ("Zastosuj zaznaczone", "Apply selected"),
    "batch_covers": ("Pobieram okładki…", "Downloading covers…"),
    "batch_applied": ("Zaktualizowano książek: {n}", "Books updated: {n}"),
    "batch_col_book": ("Książka", "Book"),
    "batch_col_proposal": ("Propozycja", "Proposal"),
    "batch_col_match": ("Zgodność", "Match"),

    # --- statystyki
    "stats_menu": ("Statystyki słuchania…", "Listening statistics…"),
    "stats_title": ("Statystyki słuchania", "Listening statistics"),
    "stats_total": ("Łącznie: {t}", "Total: {t}"),
    "stats_today": ("Dzisiaj: {t}", "Today: {t}"),
    "stats_week": ("Ostatnie 7 dni: {t}", "Last 7 days: {t}"),
    "stats_books": ("Książki w bibliotece: {n} (ukończone: {done})",
                    "Books in the library: {n} (finished: {done})"),
    "stats_last_days": ("Ostatnie 14 dni:", "Last 14 days:"),
    "stats_top": ("Najczęściej słuchane:", "Most listened:"),
    "stats_time": ("Czas słuchania", "Listening time"),

    # --- kopie zapasowe
    "backup_export": ("Zapisz kopię zapasową biblioteki…", "Save library backup…"),
    "backup_import": ("Przywróć bibliotekę z kopii…", "Restore library from backup…"),
    "backup_import_confirm": (
        "Obecna biblioteka zostanie zastąpiona zawartością kopii (jej kopia zapasowa trafi do "
        "folderu danych). Pliki audio nie są częścią kopii — muszą leżeć w tych samych miejscach. "
        "Kontynuować?",
        "The current library will be replaced with the backup's contents (a copy of it is kept in "
        "the data folder). Audio files are not part of the backup — they must be in the same "
        "locations. Continue?"),
    "backup_saved": ("Zapisano kopię ({n} książek): {path}", "Backup saved ({n} books): {path}"),
    "backup_restored": ("Przywrócono bibliotekę: {n} książek", "Library restored: {n} books"),
    "backup_failed": ("Operacja na kopii zapasowej nie powiodła się: {err}",
                      "The backup operation failed: {err}"),

    # --- błędy i ostrzeżenia
    "load_warning": ("{detail}\n\nFolder z danymi otworzysz z menu Biblioteka → Otwórz folder danych.",
                     "{detail}\n\nOpen the data folder from Library → Open data folder."),
    "unexpected_error": ("Wystąpił nieoczekiwany błąd, ale program działa dalej.\n\n{err}\n\n"
                         "Szczegóły zapisano w:\n{log}",
                         "An unexpected error occurred, but the app keeps running.\n\n{err}\n\n"
                         "Details were saved to:\n{log}"),
    "licenses_missing": ("Nie znaleziono pliku z licencjami. Zobacz "
                         "https://github.com/zetmar-collab/audiobook-player",
                         "The licenses file was not found. See "
                         "https://github.com/zetmar-collab/audiobook-player"),

    # --- element listy
    "badge_finished": ("✔ ukończony", "✔ finished"),
    "file_x_of_y": ("  ·  plik {i}/{n}", "  ·  file {i}/{n}"),

    # --- skróty i o programie
    "shortcuts_text": (
        "Spacja\t\todtwarzanie / pauza\n"
        "Enter\t\todtwórz zaznaczoną książkę\n"
        "Ctrl + ←/→\tcofnij / do przodu o 10 s\n"
        "Ctrl + Shift + ←/→\tcofnij / do przodu o 30 s\n"
        "Ctrl + PgUp/PgDn\tpoprzedni / następny rozdział lub plik\n"
        "Ctrl + ↑/↓\tgłośniej / ciszej\n"
        "Ctrl + B\t\tdodaj zakładkę\n"
        "Ctrl + Shift + B\tlista zakładek\n"
        "Ctrl + O\t\tdodaj katalog\n"
        "Ctrl + F\t\tszukaj w bibliotece\n"
        "Delete\t\tusuń zaznaczoną książkę z biblioteki\n\n"
        "Klawisze multimedialne (Play/Pauza, Następny, Poprzedni) działają globalnie, "
        "gdy opcja jest włączona w Ustawieniach.\n"
        "Pliki i katalogi można przeciągnąć na okno programu.",
        "Space\t\tplay / pause\n"
        "Enter\t\tplay the selected book\n"
        "Ctrl + ←/→\tback / forward 10 s\n"
        "Ctrl + Shift + ←/→\tback / forward 30 s\n"
        "Ctrl + PgUp/PgDn\tprevious / next chapter or file\n"
        "Ctrl + ↑/↓\tvolume up / down\n"
        "Ctrl + B\t\tadd a bookmark\n"
        "Ctrl + Shift + B\tbookmark list\n"
        "Ctrl + O\t\tadd a folder\n"
        "Ctrl + F\t\tsearch the library\n"
        "Delete\t\tremove the selected book from the library\n\n"
        "Media keys (Play/Pause, Next, Previous) work globally when the option is enabled "
        "in Settings.\n"
        "You can drag files and folders onto the window."),
    "about_title": ("O programie", "About"),
    "about_text": (
        "<b>Odtwarzacz audiobooków {version}</b><br><br>"
        "Odtwarzacz audiobooków z biblioteką, zapamiętywaniem pozycji, zakładkami "
        "i pobieraniem metadanych z serwisów polskich i zagranicznych.<br><br>"
        "Autor: Marek Zettel<br>Licencja: GPL-3.0<br>"
        '<a href="https://github.com/zetmar-collab/audiobook-player">'
        "github.com/zetmar-collab/audiobook-player</a>",
        "<b>Audiobook Player {version}</b><br><br>"
        "An audiobook player with a library, playback position memory, bookmarks "
        "and metadata lookup from Polish and international sources.<br><br>"
        "Author: Marek Zettel<br>License: GPL-3.0<br>"
        '<a href="https://github.com/zetmar-collab/audiobook-player">'
        "github.com/zetmar-collab/audiobook-player</a>"),
}

STRINGS = {
    "pl": {k: v[0] for k, v in _T.items()},
    "en": {k: v[1] for k, v in _T.items()},
}


def set_language(lang):
    global _current
    _current = lang if lang in STRINGS else "pl"


def language():
    return _current


def detect_system_language():
    """Zwraca 'pl' dla polskiego ustawienia systemu, inaczej 'en'."""
    try:
        from PyQt6.QtCore import QLocale
        code = QLocale.system().name().lower()
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
