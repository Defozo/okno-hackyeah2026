# Kontrola odtwarzalności snapshotu źródeł

Data: 3 października 2026. Sprawdzenia wykonano w osobnej kopii źródeł, z czystym katalogiem zależności JavaScript i nowym środowiskiem Python. Runtime: Node.js 24.13.0, Python 3.12.5, Windows. Kopia do publikacji nie zawiera zainstalowanych pakietów ani wygenerowanych plików.

| Sprawdzenie | Wynik |
| --- | --- |
| `npm ci` w `web/` | Instalacja 130 pakietów z lockfile zakończona powodzeniem |
| `npm run build` w `web/` | TypeScript i Vite zakończone powodzeniem; aplikacja `index-B7ZvtuTi.js`, style `index-3KQfrRp2.css` |
| Instalacja `requirements.lock.txt` w nowym venv Python 3.12 | Zakończona powodzeniem |
| `python -m pip check` | Brak konfliktów zależności |
| `python -m pytest tests -q -p no:cacheprovider` | **232 passed**, 1 ostrzeżenie, 36,72 s |
| `python -m api.importer --help` | Import i uruchomienie polecenia zakończone powodzeniem |
| `alembic upgrade head` dla nowej tymczasowej bazy SQLite | Migracje zakończone powodzeniem |
| FastAPI TestClient po migracji | `/health/ready`, zbudowany frontend `/` oraz nowa `/api/session`: HTTP 200 |
| `public-demo`: test, build, validate | **8/8** testów, poprawny worker ESM; bez konfiguracji konta hostingowego |
| Składnia `compose.yaml` i `compose.public.yaml` | `docker compose config --quiet` zakończone powodzeniem, z testowymi wartościami podstawionymi tylko do parsera |
| Statyczna kontrola źródeł | 51 plików Python, 46 JSON i 10 skryptów PowerShell poprawnych składniowo w pierwotnej kopii testowej |

Ostrzeżenie Pythona dotyczy przyszłej zmiany klienta testowego Starlette z `httpx` na `httpx2`; testy zakończyły się powodzeniem.

`npm audit` wskazał jedną zależność o poziomie high: developerski **Vite 7.1.10**. Raport wskazuje poprawkę 7.3.6 oraz kilka komunikatów dotyczących serwera developerskiego, w tym [odczyt plików przez WebSocket](https://github.com/vitejs/vite/security/advisories/GHSA-p9ff-h696-f583) i [obejście ograniczeń ścieżek w Windows](https://github.com/vitejs/vite/security/advisories/GHSA-fx2h-pf6j-xcff). Nie zmieniano zależności wyłącznie w snapshotcie, aby zachować zgodność z ocenianą wersją aplikacji. Standardowa instrukcja uruchomienia serwuje zbudowane pliki przez FastAPI; nie uruchamia serwera developerskiego Vite. Jego opcjonalnego trybu developerskiego nie należy udostępniać niezaufanym klientom przed aktualizacją.

Nie wykonywano nowej budowy obrazu Docker, pobierania dużych danych OSM/GTFS, budowy grafu OTP ani wdrożenia publicznego z tej kopii. Historyczne kontrole tych ścieżek są opisane osobno w dokumentacji. Świeży test startupu użył tymczasowej bazy i losowych danych testowych w pamięci procesu; nie odczytywał sekretów psst ani zapisanych planów użytkowniczek.

Snapshot powstał z listy dozwolonych plików. Kontrola typowych wzorców kluczy dostawców, tokenów GitHub, kluczy prywatnych, JWT, haseł w URL i trwałych cookies sesji nie wykazała trafień. Sprawdzono także brak prywatnych przypisań kont, lokalnych ścieżek profilu, środowisk, baz, backupów, oficjalnych PDF-ów i dużych danych transportowych. Jest to kontrola wzorców i zakresu plików, nie dowód wykrycia każdego możliwego sekretu. Końcowy wykaz plików i hashów jest w [SOURCE_MANIFEST.json](../SOURCE_MANIFEST.json).
