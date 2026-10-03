# Okno

**Sprawdź, co zmienić, by wrócić do pracy.** Okno łączy godziny pracy, opieki i dojazdów, wskazuje konflikt i przygotowuje konkretną propozycję dla pracodawcy. Użytkowniczka porównuje warianty, wybiera informacje do karty, zapisuje odpowiedź i sprawdza uzgodniony grafik podczas próby.

Praca kończy się o 17:00, a odbiór z dojazdem i buforem wypada o 17:45. W demonstracyjnym przykładzie przesunięcie pracy na **08:15–16:15** usuwa konflikt i zachowuje **40 godzin tygodniowo**. Wariant **08:00–16:00** daje dodatkowe 15 minut zapasu. Oba wymagają zgody pracodawcy. Kontrpropozycja 08:30–16:30 zostawia 15 minut kolizji, które Okno wykrywa przy ponownym przeliczeniu.

**[Otwórz demo](https://okno-impacther-2026.defozo.chatgpt.site/)** · **[Prezentacja i film](https://okno-impacther-2026.defozo.chatgpt.site/materialy/)**

Zespół: **DEFOZO SOFTWARE HOUSE**, **Michał Kiełtyka**. HackYeah 2026, ImpactHER: TECHNOLOGY FOR REAL CHANGE, New Idea.

## Uruchomienie lokalne

Podstawowy profil działa bez zewnętrznych API, kont użytkowniczek i modelu językowego. Przykłady są syntetyczne. Wymagania:

- Docker Desktop z kontenerami Linux oraz Compose v2.
- PowerShell 7.
- Menedżer sekretów `psst` na `PATH`, obsługujący `list --json`, `set NAZWA --stdin --quiet` i `psst NAZWA ... -- polecenie`. Użyj własnego lokalnego magazynu. Snapshot nie zawiera programu psst ani sekretów zespołu.

Z katalogu repozytorium:

```powershell
./scripts/init-secrets.ps1
./scripts/start.ps1 -Build
Invoke-RestMethod http://localhost:18430/health/ready
```

Otwórz **http://localhost:18430**. Wybierz **„45 minut do zmiany”**, potem **„Sprawdź mój plan”**. Porównaj warianty, przejdź do uzgodnień i sprawdź podgląd karty pracodawcy. Zapisz plan osobno, jeśli chcesz przejść do demonstracyjnej akceptacji, próby i kalendarza.

Pierwszy skrypt generuje pięć osobnych sekretów aplikacji i zapisuje je w psst. Zachowuje istniejące wpisy i nie wypisuje wartości. Drugi przekazuje je do Compose. Migracje uruchamia rola `okno_migrator`, a API korzysta z roli `okno_app`. Baza pozostaje w prywatnej sieci, port aplikacji jest dostępny tylko na localhost. `.env.example` dokumentuje publiczne ustawienia i nazwy sekretów.

Zatrzymanie usług z zachowaniem danych:

```powershell
psst OKNO_DB_ADMIN_PASSWORD OKNO_DB_MIGRATOR_PASSWORD OKNO_DB_APP_PASSWORD OKNO_SESSION_SECRET OKNO_ENCRYPTION_KEY -- docker compose down
```

## Rozwój bez kontenerów

Python 3.12, Node.js 24 i PowerShell 7. Dockerfile przypina Python 3.12.9 oraz Node 24.13.0. Wersje zależności zapisano w `requirements.lock.txt` i `web/package-lock.json`.

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
./.venv/Scripts/python.exe -m playwright install chromium
npm --prefix web ci
npm --prefix web run build
./scripts/init-secrets.ps1
./scripts/dev.ps1
```

`dev.ps1` wykonuje migracje SQLite i uruchamia aplikację na **http://localhost:18430**. SQLite służy do lokalnego rozwoju i testów. Compose używa PostgreSQL. Opcjonalnie, w drugim terminalu uruchom `npm --prefix web run dev`, aby pracować nad frontendem z odświeżaniem Vite. Serwer Vite przekazuje `/api` do portu 18430.

## Testy

Po zbudowaniu obrazu Docker:

```powershell
./scripts/test-docker.ps1
./scripts/browser-docker.ps1
./scripts/browser-docker.ps1 -Check keyboard-check.cjs
./scripts/browser-docker.ps1 -Check ux-regression.cjs
```

Testy przeglądarkowe wymagają działającej aplikacji. Korzystają z danych testowych, zapisują i usuwają swoje plany oraz tworzą raporty w `docs/evidence/`. Skrypt pobiera przypięty axe-core 4.10.3 i weryfikuje jego SHA-256. Oddzielny test restartu API uruchamia `./scripts/restart-docker.ps1` w profilu HTTP.

Odpowiedniki dla lokalnego środowiska Python i Node:

```powershell
./.venv/Scripts/python.exe -m pytest tests -q
npm --prefix web run build
./.venv/Scripts/python.exe scripts/browser-check.py
npm --prefix public-demo test
npm --prefix public-demo run build
npm --prefix public-demo run validate
```

Pierwsze uruchomienie testów przeglądarkowych powinno wykonać `browser-docker.ps1`, aby przygotować zweryfikowany plik axe. Pythonowy zestaw testuje solver, niezależny walidator, decyzje i kontrpropozycje, CSRF, izolację sesji, szyfrowanie, eksport, kopie, retencję i importer. [Zakres dowodów i ograniczenia](docs/VALIDATION.md) oddziela testy techniczne od badań z użytkowniczkami. [Kontrola tego snapshotu](docs/SOURCE_RELEASE_CHECKS.md) podaje świeżo wykonane sprawdzenia.

## Transport publiczny

Profil podstawowy korzysta z ręcznych czasów przejazdu dla wskazanych godzin i dat. Opcjonalny profil transportu publicznego wymaga własnego grafu OpenTripPlanner 2.7.0 oraz większej ilości pamięci: do 14 GB dla budowy grafu, osobno zasoby systemu i aplikacji.

Repozytorium zawiera skrypty, konfigurację, URL źródeł i manifest historycznej migawki. Nie zawiera OSM, GTFS ani `graph.obj`. Z katalogu projektu:

```powershell
./infra/otp/build.ps1
./scripts/start.ps1 -Transit
```

Źródła typu `latest` zmieniają się. Jeżeli pobrany plik nie zgadza się z historycznym hashem, skrypt przerwie pracę. Świadome pobranie nowej migawki wymaga `python ./infra/otp/download.py --refresh`, sprawdzenia zakresu dat, dopasowania `build-config.json` i ponownej budowy. [Instrukcja OTP](infra/otp/README.md) opisuje źródła, pamięć, ważność danych i lokalne testy. Wygaśnięcie rozkładu lub brak trasy pozostają jawnym wynikiem.

## Publiczne źródła i opcjonalne importy

Publiczny katalog zawiera pochodzenie pól i daty przeglądu. Rekord placówki nie potwierdza przyjęcia konkretnej osoby. Polecenia importera działają poza publicznym API:

```powershell
./.venv/Scripts/python.exe -m api.importer --help
```

Importer regułowy działa bez modelu. Opcjonalne Groq i Firecrawl otrzymują wyłącznie publiczne materiały. Ich klucze przekazuje operator przez psst. Prywatny grafik nie jest wejściem do modelu. [Instrukcja operatora](docs/OPERATIONS.md) opisuje import, przegląd, publikację, retencję oraz kopie.

## Architektura i dane

React, TypeScript i Vite tworzą interfejs. FastAPI obsługuje API. OR-Tools CP-SAT oblicza dopuszczalne warianty, a osobny walidator kontroluje harmonogram. PostgreSQL przechowuje zaszyfrowane plany. Playwright tworzy PDF, `icalendar` eksportuje ICS, a opcjonalny OTP wyznacza trasy.

Wynik obliczenia, jakość danych, zapisane ustalenie i rzeczywista obserwacja to osobne stany. Eksport obejmuje zatwierdzone pola i nie wysyła wiadomości. Dane formularza pozostają w pamięci przeglądarki, a analiza trafia do własnego API. Trwały zapis wymaga osobnego działania. Dostęp do zapisanych planów wiąże się z cookie tej przeglądarki.

## Publiczne demo i materiały

Brama w `public-demo/` udostępnia aplikację i materiały pod stałym adresem. Kod worker ESM i jego testy można budować bez konta hostingowego. Konfiguracja konta, wiązania magazynu i sekrety wdrożenia nie należą do tego snapshotu. [Opis bramy](public-demo/README.md) i [instrukcja operatora demo](docs/PUBLIC_DEMO.md) opisują dodatkowe wymagania wdrożenia. `compose.public.yaml` oraz `start-public.ps1` są konfiguracją operatora opublikowanego demo, a podstawowy start lokalny używa `compose.yaml`.

Interaktywne demo wymaga działającego serwera demonstracyjnego i połączenia sieciowego. Film i prezentację można otworzyć także podczas przerwy w działaniu aplikacji.

## Pochodzenie i prawa

[AI_USAGE.md](AI_USAGE.md), [PREEXISTING.md](PREEXISTING.md), [THIRD_PARTY.md](THIRD_PARTY.md) i [SOURCES.md](SOURCES.md) dokumentują autorstwo, użycie AI, biblioteki oraz dane. Snapshot zachowuje istniejące oznaczenia praw i nie nadaje nowej licencji kodowi ani zasobom zewnętrznym. Licencje zależności pozostają właściwe dla ich autorów.

Oficjalne PDF-y zadania, pełne pobrane strony, dane transportowe, binaria narzędzi, sekrety i prywatny stan środowiska nie są dołączone. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) wylicza pliki snapshotu z SHA-256; sam manifest jest wyłączony z własnej listy.
