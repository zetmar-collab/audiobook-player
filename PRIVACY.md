# Polityka prywatności — Audiobook Player

_Ostatnia aktualizacja: 12 listopada 2026_

## Krótko

Audiobook Player **nie zbiera, nie przechowuje ani nie przesyła żadnych danych
osobowych**. Nie ma kont użytkownika, logowania, reklam, analityki ani telemetrii.

## Dane przechowywane na Twoim komputerze

Aplikacja zapisuje lokalnie, wyłącznie na Twoim urządzeniu:

- listę dodanych audiobooków (ścieżki do plików, tytuły, autorzy, opisy, okładki, rozdziały
  odczytane z tagów plików),
- postęp odsłuchu, zakładki i prędkość odtwarzania zapamiętaną dla książki,
- statystyki słuchania (łączny czas, czas dzienny, czas na książkę) — liczone i przechowywane
  wyłącznie lokalnie,
- ustawienia (język, motyw, głośność, opcje odtwarzania oraz opcjonalny klucz API Google Books,
  jeśli sam go podasz),
- kopie zapasowe biblioteki (`backups\`) i dziennik błędów (`error.log`) — zawierają ścieżki do
  plików i komunikaty błędów, nigdy dane osobowe.

Lokalizacja: `%APPDATA%\AudiobookPlayer` na Windows,
`~/.local/share/AudiobookPlayer` na Linuksie.

Te dane nigdy nie opuszczają Twojego urządzenia. Nie są nam przesyłane ani
udostępniane komukolwiek. Usunięcie tego katalogu kasuje je bezpowrotnie.

## Połączenia sieciowe

Aplikacja łączy się z internetem **tylko wtedy, gdy sam poprosisz** o pobranie
metadanych lub okładki (menu kontekstowe → „Pobierz metadane z internetu" / „Pobierz okładkę"
albo Biblioteka → „Uzupełnij metadane brakujących książek", gdzie wysyłane są tytuły i autorzy
książek bez okładki lub opisu). Wysyłana jest wówczas wyłącznie fraza wyszukiwania
(tytuł/autor) oraz nagłówek `User-Agent` z nazwą i wersją programu i adresem projektu
(`AudiobookPlayer/<wersja> (+https://github.com/zetmar-collab/audiobook-player)`) do:

- lubimyczytac.pl
- upolujebooka.pl
- Audible (api.audible.com)
- Apple Books (itunes.apple.com)
- Google Books (googleapis.com; jeśli podasz własny klucz API, jest wysyłany do Google razem
  z zapytaniem)
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

_Last updated: 12 November 2026_

## In short

Audiobook Player **does not collect, store or transmit any personal data**.
There are no user accounts, no sign-in, no ads, no analytics and no telemetry.

## Data stored on your computer

The app stores locally, on your device only:

- your audiobook library (file paths, titles, authors, descriptions, cover art, chapters
  read from file tags),
- listening progress, bookmarks and the playback speed remembered for a book,
- listening statistics (total time, daily time, time per book) — computed and kept locally only,
- settings (language, theme, volume, playback options and an optional Google Books API key,
  if you enter one),
- library backups (`backups\`) and an error log (`error.log`) — they contain file paths and
  error messages, never personal data.

Location: `%APPDATA%\AudiobookPlayer` on Windows,
`~/.local/share/AudiobookPlayer` on Linux.

This data never leaves your device. It is not sent to us or shared with anyone.
Deleting that folder removes it permanently.

## Network connections

The app connects to the internet **only when you explicitly ask it to** fetch
book metadata or a cover (context menu → "Fetch metadata from the internet" /
"Fetch cover", or Library → "Fill in missing metadata", which sends the titles and authors of
books missing a cover or description). Only the search phrase (title/author) and a `User-Agent`
header with the app name, version and project address
(`AudiobookPlayer/<version> (+https://github.com/zetmar-collab/audiobook-player)`) are sent to:

- lubimyczytac.pl
- upolujebooka.pl
- Audible (api.audible.com)
- Apple Books (itunes.apple.com)
- Google Books (googleapis.com; if you enter your own API key it is sent to Google with the
  query)
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
