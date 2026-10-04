# Okno

Okno pomaga połączyć pracę, opiekę i dojazdy. Z podanych godzin i warunków wylicza konflikt, porównuje dopuszczalne zmiany i przygotowuje konkretną propozycję do rozmowy z pracodawcą. Po uzgodnieniu warunków pozwala zapisać odpowiedź, rozpocząć próbę i porównać rzeczywiste obserwacje.

**[Otwórz demo](https://okno-impacther-2026.defozo.chatgpt.site/)** · **[Prezentacja i filmy](https://okno-impacther-2026.defozo.chatgpt.site/materialy/)** · **[Pobierz kod i materiały](https://okno-impacther-2026.defozo.chatgpt.site/materialy/pakiet.zip)**

DEFOZO SOFTWARE HOUSE · Michał Kiełtyka · HackYeah 2026 · ImpactHER: Technology for Real Change · New Idea.

## Sprawdź jeden plan

W demo wybierz **„45 minut do zmiany”**, a następnie **„Sprawdź mój plan”**. Przy pracy 09:00–17:00 odbiór z dojazdem i buforem wypada 45 minut po zamknięciu placówki. Wariant 08:15–16:15 usuwa kolizję; 08:00–16:00 daje dodatkowe 15 minut zapasu. Oba zachowują 40 godzin pracy tygodniowo w tym syntetycznym przykładzie i wymagają zgody pracodawcy.

W **Uzgodnieniach** obejrzyj kartę dla pracodawcy i pobierz PDF. Możesz osobno zapisać plan, dodać odpowiedź lub kontrpropozycję, ponownie przeliczyć warunki i przejść do próby oraz kalendarza. Po demonstracji usuń swój zapis. [Instrukcja krok po kroku](docs/jury/README.md).

## Uruchomienie lokalne

Wymagania: Docker Desktop z kontenerami Linux, Compose v2, PowerShell 7 i menedżer sekretów `psst` na PATH. Użyj własnego magazynu psst obsługującego `list --json`, `set NAZWA --stdin --quiet` oraz `psst NAZWA ... -- polecenie`. Podstawowy profil działa bez zewnętrznego API i modelu językowego.

```powershell
./scripts/init-secrets.ps1
./scripts/start.ps1 -Build
Invoke-RestMethod http://localhost:18430/health/ready
```

Otwórz **http://localhost:18430**. Skrypt inicjalizujący tworzy brakujące sekrety i zachowuje istniejące. Nazwy sekretów oraz przykłady publicznych ustawień zawiera [.env.example](.env.example). Migracje wykonuje `okno_migrator`, API używa `okno_app`, a baza pozostaje w prywatnej sieci. Zatrzymanie z zachowaniem danych:

```powershell
psst OKNO_DB_ADMIN_PASSWORD OKNO_DB_MIGRATOR_PASSWORD OKNO_DB_APP_PASSWORD OKNO_SESSION_SECRET OKNO_ENCRYPTION_KEY -- docker compose down
```

Lokalne HTTPS uruchamia `./scripts/start.ps1 -Tls`; certyfikat lokalnego CA wymaga zaufania na urządzeniu. [Utrzymanie i konfiguracja](docs/OPERATIONS.md).

## Rozwój bez kontenerów

Python 3.12, Node.js 24 i PowerShell 7. Dockerfile przypina Python 3.12.9 i Node 24.13.0. Zależności są zapisane w `requirements.lock.txt` oraz `web/package-lock.json`.

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
./.venv/Scripts/python.exe -m playwright install chromium
npm --prefix web ci
npm --prefix web run build
./scripts/init-secrets.ps1
./scripts/dev.ps1
```

`dev.ps1` wykonuje migracje SQLite i uruchamia API ze zbudowanym interfejsem na porcie 18430. SQLite służy do lokalnego rozwoju i testów; Compose używa PostgreSQL. Opcjonalny `npm --prefix web run dev` uruchamia Vite z proxy `/api` do tego portu. Serwer developerski udostępniaj wyłącznie lokalnie; [informacja o zależnościach](docs/VALIDATION.md).

## Transport i publiczny katalog

Profil podstawowy przyjmuje własne, kierunkowe czasy przejazdu. Opcjonalny OpenTripPlanner 2.7.0 korzysta z OSM i GTFS. Budowa grafu wymaga do 14 GB pamięci kontenera oraz zasobów dla pozostałych usług. Dane transportowe pobiera się osobno:

```powershell
./infra/otp/build.ps1
./scripts/start.ps1 -Transit
```

[Instrukcja OTP](infra/otp/README.md) opisuje źródła, hashe, zakres dat i aktualizację grafu. Brak trasy lub wygasły rozkład jest odrębnym wynikiem. Rekord katalogu podaje źródło i datę informacji; nie jest potwierdzeniem miejsca dla konkretnej osoby. Import regułowy działa bez modelu, a opcjonalne Groq i Firecrawl przetwarzają wyłącznie publiczne materiały. [Instrukcja importu](docs/OPERATIONS.md).

## Testy

```powershell
./.venv/Scripts/python.exe -m pytest tests -q
npm --prefix web run build
npm --prefix public-demo test
npm --prefix public-demo run build
npm --prefix public-demo run validate
```

Po zbudowaniu obrazu można użyć `./scripts/test-docker.ps1`. Dla działającej aplikacji dostępne są `./scripts/browser-docker.ps1` i warianty `-Check keyboard-check.cjs` oraz `-Check ux-regression.cjs`. [Wyniki i zakres testów](docs/VALIDATION.md).

## Dane i architektura

Interfejs React/TypeScript współpracuje z FastAPI, solverem OR-Tools CP-SAT i niezależnym walidatorem harmonogramu. PostgreSQL przechowuje zaszyfrowane plany. Eksport obejmuje PDF, HTML, tekst i ICS. [Architektura i kontrakt obliczeń](docs/ARCHITECTURE.md).

Analiza trafia do własnego API. Zapis jest osobną decyzją, dostęp do planu jest powiązany z sesją przeglądarki, a eksport nie wysyła wiadomości. Prywatny grafik nie trafia do modelu językowego. Publiczne demo służy do pracy na danych testowych i zależy od działającego serwera operatora. [Działanie demo](docs/PUBLIC_DEMO.md).

[Opis produktu](docs/SUBMISSION.md) · [Materiały](docs/MATERIALS.md) · [Użycie AI](AI_USAGE.md) · [Pochodzenie](PREEXISTING.md) · [Licencje i atrybucje](THIRD_PARTY.md) · [Źródła](SOURCES.md).

Repozytorium zachowuje oznaczenia praw autorów i nie nadaje nowej licencji kodowi ani zewnętrznym zasobom. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) zawiera listę plików i ich SHA-256.
