# Okno: materiały konkursowe

**DEFOZO SOFTWARE HOUSE**, **Michał Kiełtyka**. Etap: **New Idea**.

Zobacz, jak zmiana godzin pracy usuwa 45 minut konfliktu z opieką i zachowuje 40 godzin pracy w tygodniu.

| Materiał | Plik lokalny | Publiczny adres |
| --- | --- | --- |
| Prezentacja PDF, 10 slajdów | [PDF](../output/presentation/okno-impacther-20261003.pdf) | [Otwórz prezentację](https://okno-impacther-2026.defozo.chatgpt.site/materialy/prezentacja.pdf) |
| Edytowalny PPTX z notatkami | [PPTX](../output/presentation/okno-impacther-20261003.pptx) | [Pobierz PowerPoint](https://okno-impacther-2026.defozo.chatgpt.site/materialy/prezentacja.pptx) |
| Film, 2:44, polski lektor i cicha muzyka | [MP4](../output/video/okno-demo.mp4) | [Obejrzyj film](https://okno-impacther-2026.defozo.chatgpt.site/materialy/demo.mp4) |
| Napisy | [SRT](../output/video/okno-demo.pl.srt), [VTT](../output/video/okno-demo.pl.vtt) | [VTT](https://okno-impacther-2026.defozo.chatgpt.site/materialy/napisy.vtt) |
| Interaktywne demo | [Instrukcja jurora](jury/README.md) | [Uruchom Okno](https://okno-impacther-2026.defozo.chatgpt.site/) |
| Pełny pakiet materiałów | [ZIP](../output/submission/okno-impacther-submission.zip) | [Pobierz pakiet](https://okno-impacther-2026.defozo.chatgpt.site/materialy/pakiet.zip) |
| Kod i uruchomienie | [README](../README.md) | [Repozytorium](https://github.com/Defozo/okno-hackyeah2026) |

[Publiczna strona materiałów](https://okno-impacther-2026.defozo.chatgpt.site/materialy/) i demo otwierają się bez konta. Film pokazuje rzeczywiste działanie aplikacji na przykładzie demonstracyjnym. Po pobraniu ZIP rozpakuj całe archiwum i otwórz `START.html`.

Treść odpowiada pięciu kryteriom ImpactHER. [Matryca kryteriów](jury/REQUIREMENTS.md) wskazuje oficjalne źródła i limity. [Opis projektu](SUBMISSION.md) rozwija problem, działanie produktu i planowany pilotaż.

## Kontrola materiałów

Wyniki kontroli są przypisane do konkretnych plików i dat: [prezentacja](presentation-build.json), [film](../output/video/video-validation.json), [rzeczywiste audio](evidence/audio-verification.json), [anonimowe pobrania](evidence/public-materials.json), [odtwarzanie publicznego filmu](evidence/public-materials-browser.json) i [przepływ publicznego demo](evidence/public-demo.json). [Audyt aktualizacji interfejsu](UX_PITCH_AUDIT.md) dokumentuje dwie rundy poprawek oraz zakres niezależnego przeglądu. Rozmiary i SHA-256 zawiera [manifest](materials-manifest.json).

Zapis istniejącego formularza dokumentuje `HACKTRIBE_UPDATE_RESULT.json`. Zgłoszenie pozostaje na etapie New Idea, bez osobnej finalizacji.

[Weryfikacja implementacji](VALIDATION.md), [utrzymanie publicznego demo](PUBLIC_DEMO.md), [źródła i prawa](../THIRD_PARTY.md), [wykorzystanie AI](../AI_USAGE.md), [instrukcja odtworzenia pakietu](BUILD_SUBMISSION.md). Hash ZIP i kontrola jego publicznego pobrania znajdują się w osobnych plikach `submission-package.json` oraz `evidence/public-package.json`, poza własnym archiwum.
