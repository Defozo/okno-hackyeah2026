# Biblioteki i zasoby zewnętrzne

Dokładne wersje: `requirements.lock.txt`, `web/package-lock.json`, `compose.yaml`, manifest grafu w `infra/otp/manifest.json`. Weryfikuj licencje ponownie przed dystrybucją, szczególnie dane i fonty/systemowe składniki obrazów.

| Zasób | Rola | Licencja projektu / źródło |
| --- | --- | --- |
| React, Vite, TypeScript | Interfejs i kompilacja | MIT; TypeScript Apache-2.0 |
| Radix UI, React Hook Form, Zod, Lucide | Komponenty, formularze, walidacja, ikony | MIT; Lucide ISC |
| FastAPI, Pydantic, SQLAlchemy, Alembic | API, schematy, trwałość i migracje | MIT |
| OR-Tools | Solver CP-SAT | Apache-2.0 |
| PostgreSQL | Baza prywatnych planów | PostgreSQL License |
| psycopg | Sterownik bazy | LGPL-3.0 |
| cryptography | Szyfrowanie zapisów | Apache-2.0 / BSD |
| Playwright, Chromium | Kontrolowany PDF i testy | Apache-2.0; Chromium BSD i licencje zależności |
| icalendar | Eksport zdarzeń | BSD-2-Clause |
| OpenTripPlanner | Routing na własnej infrastrukturze | LGPL-3.0 |
| OpenStreetMap / Geofabrik | Graf dróg | ODbL, © OpenStreetMap contributors |
| ZTP Kraków GTFS | Rozkłady komunikacji | Warunki źródła, patrz manifest i SOURCES.md |
| Caddy | Lokalny reverse proxy TLS | Apache-2.0 |
| axe-core | Automatyczne testy dostępności | MPL-2.0 |
| Firecrawl / Groq | Opcjonalne publiczne importy | Warunki usług dostawców; nie składniki prywatnego solvera |
| @oai/artifact-tool 2.8.59 | Nowa edytowalna prezentacja PPTX i jej render, wyłącznie narzędzie budowania | Własnościowy pakiet OpenAI dostarczony w środowisku Codex. Pakiet i jego zależności nie są redystrybuowane w ZIP |
| Node 24.19.0 i Python 3.12.14 | Środowisko nowego generatora prezentacji | Narzędzia z cache `codex-primary-runtime 26.909.12148`, poza runtime aplikacji i poza ZIP |
| ReportLab 4.4.9, pypdf 6.6.0 | Zapis PDF z renderu prezentacji i kontrola pliku | ReportLab: BSD; pypdf: BSD-3-Clause. Narzędzia budowania, poza aplikacją |
| ReportLab 4.4.3 | Historyczny generator `docs/make_submission.py` | BSD, metadane i LICENSE zainstalowanej dystrybucji |
| Pillow 12.3.0, charset-normalizer 3.5.2 | Zależności historycznego generatora PDF | Pillow: MIT-CMU; charset-normalizer: MIT. Sprawdzone metadane zainstalowanych dystrybucji |
| Georgia i Segoe UI | Fonty nowej prezentacji z zainstalowanego Windows | Systemowe fonty Microsoft. Plików fontów nie dołączono do repozytorium ani ZIP. PPTX zachowuje edytowalny tekst; zgodność wyglądu zapewnia dołączony PDF |
| FFmpeg N-115882-gc5572e329b-g0ae157b360+1 | Lokalny montaż filmu demonstracyjnego, kodowanie obrazu przez libx264 | Build zawiera `--enable-gpl --enable-version3 --enable-nonfree`; nie dołączamy ani nie redystrybuujemy jego binariów lub bibliotek. Konfiguracja jest zapisana w raporcie filmu |
| Poppler | Renderowanie i kontrola PDF w procesie budowania | GPL, narzędzie zainstalowane w środowisku, poza aplikacją |

Syntetyczne scenariusze są oznaczone jako fikcyjne. Publiczne rekordy katalogu zawierają źródła, daty i brak potwierdzenia przyjęcia. Brak licencji redystrybucji pełnej strony nie jest zgodą na kopiowanie całej treści; katalog przechowuje ograniczone fakty z przypisaniem źródła.

Lektor ElevenLabs został wygenerowany w płatnym planie payg z gotowym głosem Bella, bez klonowania. [Zasady publikacji wygenerowanej treści](https://help.elevenlabs.io/hc/en-us/articles/13313564601361-Can-I-publish-the-content-I-generate-on-the-platform) dopuszczają użycie komercyjne treści powstałych w płatnym planie poza Beta Services. Szczegóły pochodzenia i kontroli dźwięku zapisano w raporcie filmu. Podkład muzyczny jest oryginalną lokalną kompozycją i nie korzysta z Eleven Music API.

Nowa prezentacja powstaje przez `docs/build_presentation.mjs`, a dokładne wersje, hashe wejść i wynik kontroli zapisuje `docs/presentation-build.json`. [Instrukcja budowania i pakowania](docs/BUILD_SUBMISSION.md) odróżnia ten przebieg od historycznego ReportLab PDF. `docs/requirements-pdf.txt` dotyczy wyłącznie historycznego generatora; nie jest zestawem zależności nowego PPTX.

Źródła licencji narzędzi: [ReportLab 4.4.9](https://pypi.org/project/reportlab/4.4.9/), [pypdf 6.6.0](https://github.com/py-pdf/pypdf/blob/6.6.0/LICENSE), [zasady Microsoft dotyczące fontów](https://learn.microsoft.com/en-us/typography/fonts/font-faq), [licencja i konfiguracje FFmpeg](https://ffmpeg.org/legal.html). Rzeczywiste zrzuty interfejsu i tabele wyników powstały w tym projekcie. Napisy i plansze filmu korzystają z lokalnie rastrowanego Segoe UI; film zawiera polską narrację ElevenLabs (gotowy głos Bella, eleven_multilingual_v2) i oryginalny podkład instrumentalny bez zewnętrznych sampli. Pochodzenie audio oraz kontrolę miksu dokumentuje output/video/video-validation.json. Do paczki materiałów nie dodajemy binariów narzędzi budowania ani systemowych fontów.
