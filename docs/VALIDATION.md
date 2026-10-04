# Testy i ich zakres

## Ostatni zweryfikowany przebieg

4 października 2026 sprawdzono kopię źródeł publikowaną na GitHub:

| Kontrola | Wynik i środowisko |
| --- | --- |
| Backend `pytest tests -q -p no:cacheprovider` | 232 passed, 1 warning, 26,66 s; Python 3.12.5, istniejące środowisko zależności, tymczasowa baza SQLite |
| `pip check` | Brak konfliktów zależności |
| Frontend `npm ci --ignore-scripts` i `npm run build` | Instalacja z lockfile, TypeScript i Vite zakończone powodzeniem |
| Brama `npm --prefix public-demo test` | 8 testów zaliczonych |
| Brama `build` i `validate` | Poprawny moduł ESM z `default.fetch` |

Te wyniki dotyczą testów technicznych. Nie są pomiarem wpływu na zatrudnienie ani badaniem z użytkowniczkami. Aktualizacja dokumentacji nie zmienia kodu, testów ani zależności.

## Co sprawdzają testy

Zestaw backendu obejmuje konflikty godzin, koszty, pełny okres dat, DST, pojemność opieki, przekazania, niezależną kontrolę harmonogramu, trasy, brak danych i limity obliczeń. Testy API obejmują sesje, CSRF, idempotencję, kontrolę wersji, eksport, zgodę i kontrpropozycję, kopię oraz usunięcie. Importer jest sprawdzany pod kątem dozwolonych URL, cytatów, negacji, kwot, okresów i składników ceny.

Testy bramy obejmują kontrolę dostępu do operacji, nieprawidłowe adresy upstreamu, brak połączenia, pochodzenie żądania, nagłówki proxy i dozwolone pliki materiałów.

`./scripts/browser-docker.ps1` sprawdza działającą aplikację i przygotowuje przypięty axe-core 4.10.3. Warianty `-Check keyboard-check.cjs` i `-Check ux-regression.cjs` sprawdzają klawiaturę, formularze i wybrane stany interfejsu. Raporty powstają lokalnie w `docs/evidence/`. Testy używają danych syntetycznych. Automatyczne sprawdzenia nie stanowią pełnego odbioru dostępności ani testu czytnikiem ekranu.

## Zależności

W powyższym przebiegu Starlette zgłosił ostrzeżenie o przyszłej zmianie klienta testowego z `httpx` na `httpx2`. `npm audit` wykazał podatność poziomu high w developerskiej zależności Vite 7.1.10. Do czasu aktualizacji utrzymuj serwer Vite wyłącznie na localhost. Standardowy start serwuje zbudowany interfejs przez FastAPI. Zależności są przypięte w lockfile; ta publikacja ich nie zmienia.

## Odtworzenie

Polecenia instalacji oraz testów są w [README](../README.md). Testy przeglądarkowe wymagają uruchomionej aplikacji; testy OTP wymagają osobno zbudowanego grafu. Sprawdzenie nowej instalacji powinno objąć również migracje, gotowość API, zapis testowego planu, eksport i usunięcie. [Instrukcja operatora](OPERATIONS.md).
