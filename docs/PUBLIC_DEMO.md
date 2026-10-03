# Publiczne demo: działanie i utrzymanie

Docelowy adres: **https://okno-impacther-2026.defozo.chatgpt.site/**. Zespół: **DEFOZO SOFTWARE HOUSE**, Michał Kiełtyka. Strona materiałów: **https://okno-impacther-2026.defozo.chatgpt.site/materialy/**.

Publiczny odbiór zakończył się powodzeniem 3 października 2026 o 21:27:06 UTC. [Raport](evidence/public-demo.json) potwierdza świeżą sesję bez konta, zwykły DNS, walidowane HTTPS, 8 grup przepływów i 7 skanów axe bez naruszeń. Pobieranie karty PDF i ICS, zapis, decyzja, próba, izolacja sesji, kopia oraz usunięcie działały przez publiczny adres. Bieżące materiały i daty kontroli są w [MATERIALS.md](MATERIALS.md).

W raporcie jest jedno osobne ostrzeżenie platformy: restrykcyjne CSP aplikacji blokuje detekcję JavaScript wstrzykniętą przez Cloudflare. Nie osłabiono CSP. Nie wystąpiły błędy aplikacji ani inne błędy konsoli.

[Osobna próba odzyskania połączenia](evidence/public-recovery.json) zakończyła się o 18:49:27 UTC. Zrestartowano wyłącznie publiczny tunel. Zmienił on adres, connector automatycznie zarejestrował zmianę, a stała domena odzyskała gotowość po 7,38 s od żądania restartu. Następnie nowa sesja uzyskała rzeczywisty wynik OPTIMAL, konflikt 45 minut i dwa warianty. Materiały odpowiedziały HTTP 200. To pomiar jednej kontrolowanej próby, nie gwarancja czasu przywrócenia przy każdej awarii.

[Dodatkowa kontrola dostępu](evidence/public-security.json) potwierdziła 404 dla anonimowego wywołania operacyjnego, 401 dla zapisu bez sesji i 403 dla obcego Origin mimo ważnej sesji oraz tokenu CSRF. Raport opisuje te konkretne próby, nie pełny audyt bezpieczeństwa infrastruktury.

## Przepływ żądania

Stała domena HTTPS i brama są utrzymywane w Sites. Pliki prezentacji, filmu i pakietu są udostępniane z R2 przez ścieżki `/materialy/`. Dostęp do materiałów jest niezależny od pracy lokalnego solvera.

Interaktywna aplikacja działa w wydzielonym stosie Docker `okno-demo` na komputerze operatora. Żądania przechodzą przez bramę Sites, tunel ngrok i Caddy do FastAPI. Caddy wymaga sekretnego nagłówka bramy i usuwa go przed przekazaniem żądania do API. Bez niego zwraca 404. Nie jest to login jurora; użytkownik otwiera zwykły adres HTTPS bez konta.

Kontener `connector` odczytuje bieżący adres tunelu z jego lokalnego interfejsu administracyjnego i rejestruje go w stałej bramie. Ponawia rejestrację po zmianie adresu i okresowo odświeża połączenie. Sekret oraz szczegóły żądań nie trafiają do jego komunikatów diagnostycznych. Mechanizm odnawiania adresu nie usuwa zależności od działającego komputera i dostępu do internetu.

## Izolacja danych

- Publiczna wersja używa osobnej bazy i wolumenu `okno-demo`, niezależnych od lokalnej bazy wcześniejszych testów. Początkowo zawiera wyłącznie dane demonstracyjne.
- Hasła bazy, klucz szyfrowania, podpis sesji, klucz bramy i token ngrok są pobierane z psst. Nie zapisuje się ich w repozytorium, dokumentacji ani materiałach do pobrania.
- API działa jako ograniczona rola `okno_app`; migracje korzystają z osobnej roli. Ciasteczko sesji wymaga HTTPS (`Secure`), a dozwolone pochodzenie żądań jest przypisane do publicznej domeny.
- Katalog publicznych faktów i graf transportu są montowane tylko do odczytu. Publiczny stos korzysta z osobnej sieci dostępu do lokalnego OTP.
- Analiza nie oznacza zgody na zapis. Użytkowniczka zapisuje plan osobno i może go usunąć w swojej sesji. Demo należy sprawdzać na przykładach syntetycznych, bez prywatnych danych osób i pracodawców.
- Konfiguracja utrzymania przewiduje retencję planów 30 dni i szyfrowanych kopii 7 dni. Obsługuje ją osobny kontener `maintenance`.

## Uruchomienie istniejącej konfiguracji

W pełnym katalogu projektu potrzebne są działające Docker i psst, zweryfikowany obraz aplikacji oraz lokalny profil OTP z pobranym grafem. Skrypt publiczny używa obrazu aplikacji `okno-app:competition-20261003` i przypiętego digestu ngrok. Opcja `-Build` buduje obraz aplikacji z bieżących źródeł. Skrypt nie buduje grafu ani nie zakłada kont usług.

```powershell
./scripts/start.ps1 -Transit
./scripts/init-public-secrets.ps1
./scripts/start-public.ps1 -Build
```

`init-public-secrets.ps1` tworzy tylko brakujące sekrety w psst. Istniejący token ngrok pobiera z lokalnej konfiguracji narzędzia. Nie nadpisuje wcześniej zapisanych sekretów. `start-public.ps1` tworzy wydzieloną sieć dostępu do OTP, wskazuje obraz i uruchamia `compose.public.yaml` z sekretami wstrzykniętymi do procesu. Nie drukuj rozwiniętej konfiguracji kontenerów ani zmiennych środowiska, ponieważ mogą zawierać sekrety.

Stan usług można odczytać bez ujawniania konfiguracji:

```powershell
docker ps --filter label=com.docker.compose.project=okno-demo --format "table {{.Names}}\t{{.Status}}"
Invoke-RestMethod https://okno-impacther-2026.defozo.chatgpt.site/health/ready
```

Sam kod 200 z serwera nie zastępuje sprawdzenia nowej sesji przeglądarki. Po zmianie obrazu, bramy, domeny lub routingu otwórz nowe okno prywatne, uruchom przykład **45 minut do zmiany**, sprawdź warianty i podgląd karty. Przy testowym zapisie usuń utworzony plan. Wynik, datę, wersję i ograniczenia zapisz w osobnym raporcie publicznego odbioru.

## Ograniczenia

Stały adres nie oznacza hostowania obliczeń w niezależnym centrum danych. Interaktywne demo zależy od włączonego komputera, Dockera, działającego łącza, tunelu ngrok, bazy i OTP. Uśpienie lub restart komputera może przerwać analizę. Udostępnione materiały pozostają osobną ścieżką zapoznania się z produktem.

Rozkłady i graf mają ograniczony okres ważności. Nie gwarantują punktualności ani dostępności opieki. Publiczny adres nie zmienia statusu walidacji: audyt UX jest częściowy, brakuje ogłaszania wyników katalogu, a rozbieżność dotycząca edycji dat pozostaje niewyjaśniona. Nie wykonano zewnętrznych badań użyteczności, wywiadów ani rzeczywistych prób zatrudnienia.

Konfiguracja i materiały są przygotowane do demonstracji. Nie stanowią potwierdzenia operatora pilotażu, jego finansowania ani odbioru przetwarzania rzeczywistych danych. Udostępnienie nie wysyła ostatecznego zgłoszenia konkursowego.
