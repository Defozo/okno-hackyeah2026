# Publiczne demo

**[Uruchom Okno](https://okno-impacther-2026.defozo.chatgpt.site/)** bez konta albo otwórz **[prezentację i filmy](https://okno-impacther-2026.defozo.chatgpt.site/materialy/)**. W demonstracji korzystaj z danych testowych. [Instrukcja przykładu](jury/README.md).

## Przepływ żądania

Stała domena HTTPS i brama Sites przekazują żądania do wydzielonego stosu Docker `okno-demo` na komputerze operatora przez tunel ngrok i Caddy. Caddy wymaga sekretnego nagłówka bramy i usuwa go przed przekazaniem do FastAPI. Connector rejestruje aktualny adres tunelu. Brama ma ograniczoną listę przekazywanych nagłówków i plików materiałów.

Prezentacja, filmy i ZIP są przechowywane oddzielnie w R2 i udostępniane przez `/materialy/`. Mogą pozostać dostępne podczas przerwy w działaniu obliczeń. Publiczny adres nie przenosi obliczeń z komputera operatora: interaktywne demo wymaga włączonego hosta, Dockera, bazy, łącza i tunelu, a dla tras także OTP.

## Uruchomienie własnej konfiguracji

Lokalna aplikacja nie wymaga bramy. Do jej uruchomienia użyj [README](../README.md). Publiczny profil wymaga własnych kont usług, sekretów, obrazu aplikacji oraz przygotowanego grafu OTP. Konfiguracja kont i klucze nie są częścią repozytorium.

```powershell
./scripts/start.ps1 -Transit
./scripts/init-public-secrets.ps1
./scripts/start-public.ps1
```

Skrypt publiczny korzysta z istniejącego obrazu i przypiętego obrazu ngrok. Inicjalizacja sekretów zachowuje istniejące wpisy psst i korzysta z lokalnej konfiguracji ngrok. Dla innego hostingu dostosuj domenę, magazyn i kontrolowany upstream zgodnie z [opisem workera](../public-demo/README.md). Nie publikuj rozwiniętych zmiennych środowiska.

## Kontrola po zmianie

Sprawdź `/health/ready` przez docelowy HTTPS, następnie uruchom przykład w świeżej sesji, przelicz warianty, pobierz PDF i ICS oraz usuń testowy zapis. Po restarcie tunelu sprawdź, czy connector zarejestrował nowy adres. Brak połączenia z serwerem jest komunikowany jako przerwa, bez symulowania wyniku obliczeń.

Rozkłady mają określoną ważność. Trasa nie gwarantuje punktualności ani dostępności opieki. Zapisane potwierdzenia są relacją użytkowniczki. Wdrożenie z rzeczywistymi danymi wymaga własnej organizacji utrzymania, wsparcia i ochrony danych opisanej w [instrukcji operatora](OPERATIONS.md).
