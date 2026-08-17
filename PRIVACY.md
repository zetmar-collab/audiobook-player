# Polityka prywatności — Audiobook Player

_Ostatnia aktualizacja: 17 sierpnia 2026_

## Krótko

Audiobook Player **nie zbiera, nie przechowuje ani nie przesyła żadnych danych
osobowych**. Nie ma kont użytkownika, logowania, reklam, analityki ani telemetrii.

## Dane przechowywane na Twoim komputerze

Aplikacja zapisuje lokalnie, wyłącznie na Twoim urządzeniu:

- listę dodanych audiobooków (ścieżki do plików, tytuły, autorzy, opisy, okładki),
- postęp odsłuchu (numer pliku i pozycja w sekundach),
- ustawienia (język, motyw, prędkość odtwarzania, głośność).

Lokalizacja: `%APPDATA%\AudiobookPlayer` na Windows,
`~/.local/share/AudiobookPlayer` na Linuksie.

Te dane nigdy nie opuszczają Twojego urządzenia. Nie są nam przesyłane ani
udostępniane komukolwiek. Usunięcie tego katalogu kasuje je bezpowrotnie.

## Połączenia sieciowe

Aplikacja łączy się z internetem **tylko wtedy, gdy sam poprosisz** o pobranie
metadanych książki (menu kontekstowe → „Pobierz metadane z internetu"). Wysyłana
jest wówczas wyłącznie wpisana przez Ciebie fraza wyszukiwania (tytuł/autor) do:

- lubimyczytac.pl
- upolujebooka.pl
- Audible (api.audible.com)
- Apple Books (itunes.apple.com)
- Google Books (googleapis.com)
- Open Library (openlibrary.org)

Po wybraniu wyniku pobierana jest okładka i opis. Do serwisów tych nie są
wysyłane żadne informacje o Tobie, Twoim urządzeniu, bibliotece ani plikach —
tylko sama fraza wyszukiwania. Serwisy te mają własne polityki prywatności
i przetwarzają zapytania na własnych zasadach.

Poza tą jedną funkcją aplikacja nie nawiązuje żadnych połączeń sieciowych.

## Pliki audio

Aplikacja odczytuje pliki audio z katalogów, które sam wskażesz. Pliki są
odtwarzane lokalnie i nigdy nie są wysyłane, kopiowane ani modyfikowane.
Aplikacja nigdy nie kasuje Twoich plików — usunięcie pozycji z biblioteki
usuwa tylko wpis w bazie, nie plik na dysku.

## Dzieci

Aplikacja nie zbiera danych od nikogo, w tym od dzieci.

## Kontakt

Pytania: zetmar@gmail.com
Kod źródłowy (GPL-3.0): https://github.com/zetmar-collab/audiobook-player

---

# Privacy Policy — Audiobook Player

_Last updated: 17 August 2026_

## In short

Audiobook Player **does not collect, store or transmit any personal data**.
There are no user accounts, no sign-in, no ads, no analytics and no telemetry.

## Data stored on your computer

The app stores locally, on your device only:

- your audiobook library (file paths, titles, authors, descriptions, cover art),
- listening progress (file index and position in seconds),
- settings (language, theme, playback speed, volume).

Location: `%APPDATA%\AudiobookPlayer` on Windows,
`~/.local/share/AudiobookPlayer` on Linux.

This data never leaves your device. It is not sent to us or shared with anyone.
Deleting that folder removes it permanently.

## Network connections

The app connects to the internet **only when you explicitly ask it to** fetch
book metadata (context menu → "Fetch metadata from the internet"). Only the
search phrase you typed (title/author) is sent to:

- lubimyczytac.pl
- upolujebooka.pl
- Audible (api.audible.com)
- Apple Books (itunes.apple.com)
- Google Books (googleapis.com)
- Open Library (openlibrary.org)

After you pick a result, its cover image and description are downloaded. No
information about you, your device, your library or your files is sent to these
services — only the search phrase itself. These services have their own privacy
policies and handle queries under their own terms.

Apart from this single feature, the app makes no network connections.

## Audio files

The app reads audio files from folders you choose. Files are played locally and
are never uploaded, copied or modified. The app never deletes your files —
removing an item from the library removes only the database entry, not the file
on disk.

## Children

The app collects no data from anyone, including children.

## Contact

Questions: zetmar@gmail.com
Source code (GPL-3.0): https://github.com/zetmar-collab/audiobook-player
