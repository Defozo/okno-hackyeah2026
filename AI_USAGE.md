# Wykorzystanie AI

DEFOZO SOFTWARE HOUSE, Michał Kiełtyka. Codex wspierał odczyt wymagań, koncepcję, implementację frontendu i backendu, model ograniczeń, testy, dokumentację i materiały prezentacyjne. Autor odpowiada za końcowe rozwiązanie.

## Działanie aplikacji

Wykonalność oblicza OR-Tools CP-SAT z niezależnym walidatorem. Opcjonalny model Groq odczytuje publiczne materiały, a Firecrawl może pobierać publiczne strony. Proponowane pola wymagają cytatu, walidacji i przeglądu. Etykiety korpusu testowego powstały z pomocą AI.

Prywatne grafiki, dane rodziny i kalendarze nie są przesyłane do modelu językowego. Sekrety są przekazywane przez psst do odpowiedniego procesu, poza frontendem.

## Prezentacja i audio

Codex wspierał tekst prezentacji, scenariusze i montaż z nagrań aplikacji. Bazowy film używa polskiego lektora ElevenLabs: gotowy głos Bella, `eleven_multilingual_v2`, bez klonowania głosu. Jego podkład instrumentalny skomponowano lokalnie bez zewnętrznych sampli. Analizę dźwięku wspierał Gemini 3.8 Flash.

Dodatkowy wariant muzyczny korzysta z muzyki i wokalu Eleven Music oraz autorskiego tekstu przygotowanego z pomocą AI. Grafika coveru powstała z użyciem image_gen. Filmy i demo pokazują dane syntetyczne. [Atrybucje i licencje](THIRD_PARTY.md).
