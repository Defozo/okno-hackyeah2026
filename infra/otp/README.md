# OpenTripPlanner dla Okna

Wersja OTP: 2.7.0. Źródła: OpenStreetMap przez Geofabrik oraz trzy feedy ZTP Kraków. [manifest.json](manifest.json) zawiera URL, SHA-256, zakres danych i hash zbudowanego grafu. Bieżący graf obejmuje 2026-10-02 do 2026-11-15. Poza tym zakresem adapter zwraca `stale`.

## Pobranie i budowa

Z katalogu projektu, przy działającym Docker Desktop i Pythonie z zależnościami:

```powershell
.\infra\otp\build.ps1
```

Skrypt pobiera brakujące wejścia, kontroluje zgodność z manifestem, kopiuje konfigurację i buduje przypiętym digestem obrazu. Budowa ma limit 14 GB RAM kontenera i 12 GB sterty JVM. Do uruchomienia Compose przeznacza 12 GB RAM, w tym 10 GB sterty. Potrzebne są również zasoby dla API, bazy i systemu.

Następne wywołanie zachowuje wejścia. Jeśli plik wskazany przez `latest` zniknął lokalnie i pobrany egzemplarz różni się od hash w manifeście, skrypt przerywa. To wykryta zmiana źródła, nie automatyczna zgoda na podmianę.

Jawna aktualizacja migawki:

```powershell
python .\infra\otp\download.py --refresh
.\infra\otp\build.ps1
```

Przed rozszerzeniem okresu zmień `transitServiceStart` i `transitServiceEnd` w `build-config.json`, pobierz feedy obejmujące okres i przebuduj graf. `pin_graph.py` zapisuje końcową ważność, digest obrazu i hash grafu. Przechowuj poprzedni manifest z raportem dla odtwarzalności wcześniejszych decyzji. Duże wejścia i graf w `data/` są wyłączone z wersjonowania.

## Profil aplikacji

Uruchom inicjalizację sekretów i bazę zgodnie z głównym README. Następnie:

```powershell
$env:ROUTING_MODE = 'otp'
psst OKNO_DB_ADMIN_PASSWORD OKNO_DB_APP_PASSWORD OKNO_DB_MIGRATOR_PASSWORD OKNO_SESSION_SECRET OKNO_ENCRYPTION_KEY -- docker compose --profile transit up -d
```

OTP ma pozostać w sieci prywatnej. API używa `OTP_URL=http://otp:8080`, a manifestu w `/app/otp-data/manifest.json`. Brak sekretu dostawcy nie blokuje własnego OTP.

## Lokalna weryfikacja grafu

Podany poniżej port służy wyłącznie diagnostyce na localhost. Jeśli kontener `okno-otp-validation` już działa, wykorzystaj go zamiast tworzyć drugi. Istniejący zatrzymany kontener uruchom przez `docker start okno-otp-validation`. Polecenie `docker run` poniżej jest przeznaczone dla pierwszego uruchomienia. Po testach `docker stop okno-otp-validation` zwalnia zasoby, pozostawiając usługę OTP z Compose.

```powershell
$otpDataPath = [IO.Path]::GetFullPath((Join-Path $PWD 'infra/otp/data'))
docker run -d --name okno-otp-validation --memory=12g -e JAVA_TOOL_OPTIONS=-Xmx10g -p 127.0.0.1:18440:8080 --mount "type=bind,source=$otpDataPath,target=/var/opentripplanner,readonly" opentripplanner/opentripplanner:2.7.0@sha256:640870b240ad206d05634e7a066588804c6e23abebf37cbc02b0c9ba66073486 --load --serve
$env:OTP_URL = 'http://127.0.0.1:18440'
python -m infra.otp.verify_live
python -m infra.otp.verify_hydration
```

`verify_live` sprawdza dwie godziny, wymagane przybycie, kierunek powrotny i wygaśnięcie. `verify_hydration` wykonuje ponowne obliczenie tras wszystkich startów w małym rzeczywistym grafie, uruchamia solver i niezależny walidator. Raporty obok skryptów zawierają faktyczne statusy. Nie gwarantują punktualności pojazdu ani pokrycia każdej lokalizacji.

Zapas i przekazanie pozostają osobne. Dla `arrive_by` adapter odejmuje je od wymaganej godziny przed pytaniem do OTP. Dla `depart_after` uwzględnia początkowe oczekiwanie. Band dotyczy dokładnej minuty wyjazdu, kierunku i dnia. Przesunięcie zmiany uruchamia nowy odczyt. Brak trasy nie zamienia się automatycznie w samochód ani sztuczny ręczny czas. Bilet i ulgi wymagają osobnego potwierdzenia ceny.

Licencje: [OSM ODbL i atrybucja](https://www.openstreetmap.org/copyright). Publiczny [katalog ZTP](https://gtfs.ztp.krakow.pl/) nie zastępuje sprawdzenia warunków redystrybucji przed publikacją feedu lub grafu. Ten projekt nie publikuje kopii tych danych.
