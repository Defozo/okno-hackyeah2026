# Okno: walidacja techniczna i zakres dowodów

Zespół: **DEFOZO SOFTWARE HOUSE**. Jedyny członek: **Michał Kiełtyka**, zgodnie z [TEAM.json](../TEAM.json). Stan: 2026-10-03. Wymagania pochodzą z [wybranego planu](../official-2026-10-03/PLAN.md). Mapę funkcji do implementacji zawiera [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

Zapisany przebieg potwierdza tylko faktycznie sprawdzony zakres i wersję. Obecność testu lub skryptu nie jest dowodem jego pomyślnego wykonania. Końcowy zbiorczy raport odbioru ma ścieżkę [evidence/verification.json](evidence/verification.json); zawarte w nim daty i wyniki należy odczytywać razem z raportami szczegółowymi. Brak raportu albo brak danej kontroli oznacza brak zbiorczego potwierdzenia tej kontroli.

## Rodzaje danych i dowodów

| Materiał | Co jest rzeczywiste | Co jest syntetyczne lub nieudowodnione |
| --- | --- | --- |
| [Przykłady solvera](../data/synthetic/) i testy API | Wykonany kod, odpowiedzi API, eksporty i kontrola ograniczeń | Osoby, oferty pracy, opieka, ceny, zgody, odmowy i wpisane obserwacje |
| [Przebieg przeglądarkowy](evidence/browser-report.json), zrzuty, [PDF karty](evidence/employer-card.pdf), [ICS](evidence/trial-calendar.ics) | Interakcje z lokalną aplikacją i faktycznie pobrane pliki | Nie potwierdzają prawdziwego uzgodnienia ani osiągniętych godzin pracy |
| [Regresje UX](evidence/ux-regression.json) i [pierwszy niezależny przegląd AI](evidence/ux-audit-initial.json) | Rzeczywiste analizy pustego i poprawionego planu, dostępność menu, błędy dat, jawnie kontrolowane odpowiedzi i korekty interfejsu | Przegląd asystenta AI nie jest sesją z uczestniczką, testem czytnikiem ekranu ani certyfikacją WCAG |
| [Manifest OTP](../infra/otp/manifest.json), [trasy](../infra/otp/live-verification.json) | Graf OSM/GTFS, rzeczywiste zapytania do uruchomionego OTP, daty i kierunki | Rozkład nie gwarantuje punktualności pojazdu; test nie jest przejazdem w terenie |
| [Hydratacja tras i solver](../infra/otp/hydration-verification.json) | Zapytania tras dla rzeczywistych punktów i godzin oraz wynik solvera | Potrzeby dwóch podopiecznych, placówki w scenariuszu, ich ceny i zgody są syntetyczne |
| [Publiczny rekord żłobka](../data/catalog/zlobek6.json) | Publiczny URL, pobrana informacja o godzinach, data przeglądu i fragment źródła | Brak potwierdzenia przyjęcia konkretnej osoby, ceny i wyjątków kalendarza |
| [Groq benchmark](../data/extraction/groq-benchmark.json), [Firecrawl](../data/extraction/live-firecrawl-result.json) | Wywołania usług na publicznych materiałach | Nie są niezależnym audytem redaktorskim, badaniem reprezentatywnym ani przetwarzaniem prywatnych grafików |
| [RESEARCH.md](RESEARCH.md) i [pilot-template.json](pilot-template.json) | Gotowy protokół i pusty szablon pomiaru | 0 wywiadów, 0 sesji z osobami spoza zespołu, 0 rzeczywistych prób zatrudnienia |

## Pokrycie testami

| Wymaganie planu | Testy i kontrolowane przypadki |
| --- | --- |
| Pełny czas, twarde warunki i opieka | [test_solver.py](../tests/test_solver.py): konflikt 45 minut, kontrpropozycja 15 minut, zamknięcie po pierwszych 28 dniach, pojemność, zajętość opiekuna, opieka dorosłych, praca zdalna bez automatycznej opieki, noc i DST, kurs przed pracą, odpoczynek z dojazdem, opieka także w dni bez pracy |
| Przekazania i kilka miejsc | Ten sam zestaw: jawne przekazanie, brak odcinka kierunkowego, dwa miejsca i różny rozkład, brak możliwości jednoczesnego przejazdu opiekuna z dwóch miejsc, niezależna kontrola własnej pojemności |
| Braki i wyniki solvera | Nieznana cena lub godzina, wygasłe dane, `UNKNOWN` przy limicie, niepełna optymalizacja, odmówiona propozycja i zmieniona kolejność celów. `INFEASIBLE` dotyczy sprawdzonej domeny |
| Rygor optymalizacji | Mała domena porównana z pełnym ręcznym wyliczeniem; zaostrzenie ograniczeń nie dodaje rozwiązań; etap minimum utrwalany wyłącznie z dowodem optimum |
| Niezależny walidator | Celowo uszkodzone godziny, koszt, transfer i przypisania w `test_independent_validator_rejects_corruption` oraz przypadki samodzielnej opieki |
| Trasy | [test_routes.py](../tests/test_routes.py): odjazd, przybycie, kierunek, ręczne zakresy i noc, DST, wygasły feed, pusta odpowiedź, awaria i rezerwa przekazania/bufora. [test_transit.py](../tests/test_transit.py): ponowne obliczenie wszystkich startów oraz brak deklaracji pełnej domeny po limicie |
| Wersje, decyzje i próba | [test_api.py](../tests/test_api.py): zapis, akceptacja, odmowa, kontrpropozycja, obserwacja, import bez przeniesienia aktualnej zgody, konflikt wersji i idempotencja |
| Dostęp i eksport | `test_api.py`: inna sesja, CSRF, szyfrowanie, dozwolone pola odbiorcy, zgodność podglądu i eksportu, unieważnienie podglądu, usunięcie oraz brak odtworzenia planu przez powtórzony zapis |
| Kopie i retencja | [test_maintenance.py](../tests/test_maintenance.py): zaszyfrowana kopia, odtworzenie respektujące usunięcia i usuwanie wygasłych planów |
| Publiczne importy | [test_importer.py](../tests/test_importer.py): domeny, prywatne IP, sanitizacja, niepoparte fragmentem wartości i negacja, kwoty i okres ceny, CSV z brakami, przegląd/publikacja, wygasanie pól i oznaczone przypadki polskie |
| Przeglądarka i dostępność | [browser-check.cjs](../scripts/browser-check.cjs): konflikt i alternatywy, podgląd odbiorcy, rzeczywisty PDF, dobrowolny zapis, zgoda, baza próby, pusty formularz wyniku, obserwacja i ICS; axe, viewport 320/360 px, błędy strony i konsoli |

Końcowy przebieg `scripts/test-docker.ps1`, powtórzony po drugiej rundzie korekt UX, zakończył się wynikiem **232 passed w 29,62 s**, z jednym ostrzeżeniem o przyszłej zmianie klienta testowego Starlette. Pełny zapis: [pytest-output.txt](evidence/pytest-output.txt). Zestaw obejmuje także przerwane połączenie podczas zapisu, odtworzenie potwierdzeń przekazania opieki, przenośny UTC w ICS przy zmianie czasu, datę obserwacji po północy w Warszawie, blokowanie przyszłych obserwacji oraz nowe regresje znaczenia godzin i składnika ceny w importerze. Testy API w zestawie używają izolowanej bazy SQLite. PostgreSQL sprawdzono osobno przez działającą aplikację, zgodnie z raportami poniżej.

## Zweryfikowane integracje i ograniczenia

[Raport OTP](../infra/otp/live-verification.json) zapisuje zapytania dla 5 października 2026: dwie godziny poranne, przybycie na wskazaną godzinę, kierunek powrotny oraz zachowanie po wygaśnięciu. [Manifest](../infra/otp/manifest.json) przypina OTP 2.7.0, hashe wejść i grafu; sprawdzony zakres grafu to 2026-10-02 do 2026-11-15. Poza nim nie należy korzystać z ostatniego poprawnego czasu. Ważność danych wymaga ponownego sprawdzenia przy późniejszym użyciu raportu.

[Przebieg hydratacji](../infra/otp/hydration-verification.json) z 2026-10-03 obejmuje dwa miejsca opieki, jeden poniedziałek i trzy dozwolone starty. Zapisano 18 zapytań, pełne ukończenie hydratacji, 6366 ms jej czasu oraz status solvera `OPTIMAL` z walidacją harmonogramu. Ten pomiar nie jest testem szybkości 28-dniowego scenariusza ani dowodem skuteczności realnej opieki.

Wcześniejszy [test przez lokalne HTTPS](evidence/live-api-tls.json) objął TLS 1.3 z weryfikacją lokalnego CA i nazwy localhost, flagi cookie, 18 rzeczywistych zapytań OTP, solver i walidator, zapis/odczyt w PostgreSQL, idempotencję, izolację sesji, dokładny eksport i usunięcie. Analiza tras oraz wariantu zajęła 12,957 s. Certyfikatu CA nie instalowano globalnie. Backend pozostał bez zmian podczas późniejszych korekt UX; najnowsze testy interfejsu wykonano osobno przez lokalne HTTP. To dowód lokalnego HTTPS dla wskazanego przebiegu API, bez publikacji w internecie.

[Kontrola przechowywania](evidence/storage-report.json) potwierdziła rolę `okno_app` bez uprawnień superuser, tworzenia baz i ról, istnienie zaszyfrowanej kopii z serwisu utrzymania oraz jej poprawne odszyfrowanie do oczekiwanego schematu. Raport nie zawiera klucza ani prywatnych rekordów. [Manifest uruchomionej wersji](evidence/runtime-manifest.json) porównuje hashe plików API i zbudowanego frontendu z katalogiem projektu.

[Test rzeczywistego restartu](evidence/restart-report.json) zapisał syntetyczny plan, uruchomił API ponownie i odczytał ten sam plan w tej samej sesji. Dane, wersja i wybór wariantu zostały zachowane; plan testowy następnie usunięto. Poświadczenia klienta pozostawały wyłącznie w pamięci. Końcowy [profil uruchomienia](evidence/running-profile.json) pozostawiono na `http://localhost:18430` z rzeczywistym OTP. Port jest lokalny; profil HTTPS został wcześniej osobno przetestowany i można go uruchomić przełącznikiem `-Tls`.

[Publiczny rekord Żłobka Samorządowego nr 6](../data/catalog/zlobek6.json) zawiera godzinę źródła 06:00 do 17:00, sprawdzenie 2026-10-03 i termin ponownego przeglądu do 2026-10-10. Pozostawia brak ceny, przyjęcia oraz wyjątków. Katalog pokazuje te braki; nie nazywa rekordu rezerwacją.

[Raport Groq](../data/extraction/groq-benchmark.json) zapisuje **64/67** zgodnych przypadków dla `openai/gpt-oss-120b` wraz z walidatorem. Korpus obejmuje 36 URL, 6 dodatnich przykładów godzin, 9 cen z okresem i składnikiem, rzeczywistą negację godzin oraz wyłączenie ceny z pakietu. Trzy odpowiedzi zostały bezpiecznie odrzucone jako `ImportRejected`: dwa błędne składniki ceny i pominięta negacja ceny. Odrzucenia są porażkami pomiaru, a nie poprawnymi pustymi polami. Wśród zwróconych wyników nie było rozbieżności z etykietami. Pierwotne 50/50 oraz pośrednie 54/67 i 63/67 zachowano; poprawki nie polegały na zastąpieniu błędów zerami. Przeważają nadal strony dotyczące opieki i brakujące wartości, więc wynik nie jest reprezentatywnym oszacowaniem jakości ani niezależnym audytem ludzkim. Dodatkowy [korpus syntetyczny](../data/extraction/adversarial-pl.json) sprawdza trudne konstrukcje i negację. Publiczne pola wymagają pochodzenia i osobnego przeglądu. Przykład Firecrawl jest zapisem pobrania, a nie publikacją rekordu.

[Karta KIDS SPACE Barska](../data/catalog/kids-space-barska.json) i końcowy test przeglądarki pokazują 500 zł jako jednorazową opłatę rekrutacyjną. Koszt bieżącej opieki, wyżywienia i przyjęcie konkretnej osoby pozostają jawnie niepotwierdzone. Przegląd źródła wykonał asystent AI, co zapisano w historii redakcyjnej. Walidator wiąże kwotę, okres i składnik z tym samym fragmentem oraz odrzuca godziny zamknięcia jako godziny usługi.

## Interfejs, dostępność i przegląd końcowy

Najnowszy lokalny [przebieg przeglądarki](evidence/browser-report.json) z 2026-10-03, godz. 16:37 UTC, przez `http://localhost:18430` potwierdził dziewięć grup funkcji: własną ofertę i braki danych, konflikt i warianty, dokładny PDF, zapis i akceptację, próbę i obserwację, ICS, kopię/usunięcie/import, publiczny katalog oraz poprawne rozdzielenie składnika ceny. Axe 4.10.3 nie zgłosił naruszeń na ośmiu sprawdzonych ekranach. Nie wystąpiły błędy strony ani nieoczekiwane błędy konsoli. Wstrzyknięto jeden kontrolowany HTTP 429 podczas zapisu odpowiedzi; błąd pozostał dostępny w dialogu, wpisana odpowiedź nie zniknęła, a ponowienie przez rzeczywiste API zakończyło się HTTP 200. Oczekiwany wpis konsoli o tym 429 jest zapisany osobno. Wyniki nie mają poziomego przewijania przy 320/360 px i powiększeniu CSS do 200%. [Nagranie](evidence/demo-recording.webm) trwa 58,00 s, ma 5 849 750 bajtów i pokazuje faktycznie wykonany test na tej wersji aplikacji z danymi demonstracyjnymi. Obejrzano także zapisaną [klatkę nagrania](evidence/demo-frame-reviewed.png).

Osobny [test klawiatury](evidence/keyboard-report.json) przeszedł bez używania wskaźnika, programowego ustawiania fokusu ani przygotowania planu przez API. Obejmuje odnośnik pomijający nawigację, wpisanie własnej oferty domowej, analizę, jawną zgodę na zapis, zarządzanie planem i usunięcie ze sprawdzeniem pustej listy. W dialogu sprawdzono 14 przejść Tab/Shift+Tab i powrót fokusu po Escape. Test wykrył i doprowadził do naprawy braku tego powrotu. Zapis semantyki dostępności w raporcie nie jest badaniem czytnikiem ekranu.

[Regresje UX](evidence/ux-regression.json) sprawdziły zamknięte i otwarte menu przy 390 px, Tab/Shift+Tab/Escape, drzewo dostępności oraz przejście przez szerokości 390/1440/390 px. Nieprawidłowa data otrzymuje polski komunikat powiązany z polem i podsumowaniem błędów. Po wpisaniu dwóch dat znak po znaku i ich poprawieniu pozostałe dane zachowały się, a rzeczywiste API zwróciło poprawnie zweryfikowany wariant `OPTIMAL`. Druga rzeczywista analiza potwierdziła, że pusty plan kieruje do uzupełnienia danych bez fałszywej deklaracji limitu czasu. Osobno sprawdzono siedem jawnie zasymulowanych odpowiedzi statusów. Kontrolowany HTTP 429 zapisu planu zachował zgodę i dane w dialogu; rzeczywiste ponowienie zwróciło 200, po czym plan testowy usunięto. Wszystkie pięć sprawdzonych ekranów axe nie miało naruszeń. Nie sumujemy tych ekranów z głównym przebiegiem jako liczby unikalnych widoków.

Druga runda regresji potwierdziła także nazwę pola, minimum i powiązanie błędu dla wartości -1 wymaganego płatnego czasu pracy oraz budżetu. Poprawienie godzin na 0 i pozostawienie pustego budżetu usuwa błędy. Nowo otwarte przykłady używają polskich etykiet miejsc i podopiecznych. [Test kontraktu etykiet](evidence/example-label-contract.json) obejmuje trzy przykłady, zachowanie pozostałych danych i unikanie kolizji nazw; jest to test offline z **0 wywołań API**. Dodatkowe dwie rzeczywiste analizy w raporcie UX porównały oryginalny oraz przetłumaczony przykład `single-parent`: status `OPTIMAL`, konflikty, oba harmonogramy, koszty, metryki i etapy dowodu pozostały równoważne. Końcowy raport UX obejmuje łącznie **4 rzeczywiste analizy**, **7 jawnych mocków odpowiedzi statusów** oraz 13 aktualnych zrzutów. Tłumaczenie przy otwieraniu przykładu nie zmienia źródłowych fixture ani referencji benchmarku.

Osobny asystent AI przeprowadził [początkowy audyt](evidence/ux-audit-initial.json) w izolowanej przeglądarce, na danych syntetycznych. Zgłosił trzy problemy: dostępność zamkniętego menu mobilnego, techniczny angielski błąd daty oraz utożsamianie braków danych z limitem analizy. [Plan korekt](evidence/ux-correction-plan.md) zachowuje pochodzenie tych ustaleń. W trakcie regresji dodatkowo wykryto i poprawiono wpisywanie separatora dat, kontrast nieaktywnych dni oraz widoczność błędów w dialogach zapisu i odpowiedzi. Te dodatkowe ustalenia pochodzą z testów wdrożenia, nie z raportu niezależnego audytora. [Drugi audyt](evidence/ux-audit-intermediate.json), ze statusem `partial`, potwierdził poprawę menu i pustego planu oraz wskazał ogólny komunikat wartości -1 i angielskie etykiety przykładu. Druga runda korekt usunęła te problemy bez zmiany reguł serwera ani obliczeń.

[Końcowy świeży audyt AI](evidence/ux-audit-final.json), po dwóch rundach korekt, nadal ma status **`partial`** i dwa zgłoszenia. Zachowano pełny oryginalny raport. [Oddzielna reprodukcja](evidence/ux-final-findings.json) nie zmienia jego treści ani oceny audytora:

| Zgłoszenie końcowego audytu | Oddzielnie zaobserwowany wynik i status |
| --- | --- |
| F1, wysoki priorytet: analiza poprzednich dat po wpisaniu końca wcześniejszego od początku | **Nie odtworzono dwoma opisanymi metodami.** Zwykłe `fill` oraz klawiaturowa zmiana segmentu dnia z prawdziwymi zdarzeniami zachowały wpisane 2026-10-01 po opuszczeniu pola, pokazały błąd zakresu, wyłączyły analizę i nie wysłały żądania. Kontrole dodatnie z końcem 2026-10-08 wysłały i przeanalizowały właśnie okres 05–08. Nie jest to dowód wykluczenia każdego możliwego sposobu reprodukcji. |
| F2, średni priorytet: brak ogłoszenia wyników filtrowania katalogu | **Potwierdzona otwarta wada dostępności.** Widoczne wyniki i komunikat pustej listy zmieniają się, lecz nie są ogłaszane przez region `aria-live`/`status`; pozostaje w nim wcześniejszy komunikat analizy. |

Oddzielna kontrola dat stwierdziła również brak jawnych `aria-invalid` i `aria-describedby` dla błędu kolejności zakresu. Komunikat jest częścią etykiety obejmującej pole i jego nazwy dostępności; nie sprawdzono rzeczywistego odsłuchu czytnikiem ekranu. Po wyjściu z formularza i powrocie wpisana data pozostaje zachowana, lecz lokalny błąd znika i przycisk staje się aktywny. Nie klikano tej niepoprawnej próby po ponownym otwarciu formularza, więc jej dalszy przebieg nie został zweryfikowany. Rozbieżność z relacją audytora pozostaje niewyjaśniona. Te obserwacje nie zostały ukryte pod wynikiem pomyślnej regresji.

Zgodnie z ustalonym limitem wykonano dwie rundy korekt i po końcowym audycie nie prowadzono trzeciej. Cykl audytu zamknięto ze statusem `partial`. Pozostałe uwagi są jawne, a pełny odbiór dostępności i zakończenie wszystkich napraw **nie zostały osiągnięte**. Końcowy audyt nie obejmował wszystkich formularzy, trwałego zapisu, importu, eksportu ani rzeczywistego powiększenia 200%; te przepływy mają odrębne dowody automatyczne. Audytorem był asystent AI, nie uczestniczka badania użyteczności.

Klawiatura, poprawne etykiety pól, przywracanie fokusu dialogów, komunikaty statusu i reflow są elementami implementacji. Automatyczne axe nie zastępuje niezależnego testu czytnikiem ekranu, rzeczywistym telefonem i użytkowniczkami. Nie deklarujemy pełnej certyfikacji WCAG ani samodzielnego ukończenia przez planowane 10 z 12 osób.

## Wydajność i limity

[benchmark.py](../data/synthetic/benchmark.py) tworzy referencję 28 dni, 3 podopiecznych, 3 opiekunów i 10 zasobów, z jawnie ograniczonym zbiorem zgodnych przydziałów oraz 5 początkami pracy. Zapisuje sprzęt, runtime, pierwszy przebieg, importy, liczbę próbek, medianę i p95. Raport wynikowy ma ścieżkę `data/synthetic/benchmark-results.json`. Cel p95 do 3 s jest wymaganiem odbioru, nie domyślnym twierdzeniem. O jego osiągnięciu decyduje pole `target_met` danego raportu.

Końcowa [referencja](../data/synthetic/benchmark-results.json) na Intel Core i9-14900KF w WSL2/Linux: 20 ciepłych prób, mediana 2,678 s, p95 2,872 s, maksimum 2,954 s; pierwszy solve 2,630 s i osobno import 2,313 s. Wszystkie 21 analiz miały status OPTIMAL, trzy warianty i poprawną niezależną walidację. **Cel p95 do 3 s został spełniony w tej próbie.** [Demo mierzone osobno](../data/synthetic/benchmark-demo-results.json) miało p95 0,060 s w 20 próbach; ta liczba nie zastępuje referencji. Zoptymalizowany i pełny model porównano testami zgodności na czterech scenariuszach, w tym całej referencji. Dodatkowe cztery porównania potwierdziły zgodność pełnych optimum leksykograficznych z domyślnymi nastawami CP-SAT. Ostateczna optymalizacja wyłącza probing i symetrię dla faz optymalizacyjnych, zachowując presolve oraz domyślne nastawy diagnozy. Scenariusz i niezależny walidator pozostały bez zmian.

Pomiar solvera nie zawiera HTTP i sieci OTP. Pierwsze wywołanie po imporcie nie jest czystym startem całego kontenera. Wyniki współdzielonego hosta nie przenoszą się automatycznie na hosting docelowy. Cała analiza API ma konfigurowalny budżet czasu obejmujący hydratację i proces solvera; przekroczenie limitu pozostawia wynik nierozstrzygnięty. Domenę kandydatów i liczbę uruchomień ograniczono, zamiast uruchamiać nieograniczone procesy.

## Odtworzenie kontroli

Z katalogu projektu, po uruchomieniu opisanym w [README](../README.md):

```powershell
./.venv/Scripts/python.exe -m pytest tests -q
npm --prefix web run build
./.venv/Scripts/python.exe scripts/browser-check.py
./.venv/Scripts/python.exe data/synthetic/benchmark.py --samples 10
```

Alternatywnie użyj `scripts/test-docker.ps1` i `scripts/browser-docker.ps1` dla kontenerów. Osobny test klawiatury uruchamia `scripts/browser-docker.ps1 -Check keyboard-check.cjs`, a regresje UX `scripts/browser-docker.ps1 -Check ux-regression.cjs`; zgodność uruchomionych plików sprawdza `scripts/verify-runtime.ps1`. Przebiegi przeglądarki wymagają lokalnej aplikacji na `http://localhost:18430`. Uruchamiaj je kolejno, aby kontrola interfejsu nie konkurowała o ograniczoną pulę analiz API. Lokalny profil TLS i zmienne procesu testowego opisano w README. Raporty tras odtwarzają polecenia w [instrukcji OTP](../infra/otp/README.md). Ponowne uruchomienie zewnętrznej ekstrakcji wymaga wybranych kluczy psst i nie jest wymagane do pracy ręcznego profilu core.

Przed odbiorem konkretnej wersji sprawdź także zapis/odczyt po ponownym otwarciu aplikacji, kopię/import, usunięcie, błędną wersję, odmowę zasobu, kontrpropozycję, blokadę i naprawę próby oraz odświeżenie katalogu. Zrzuty i pliki PDF/ICS muszą pochodzić z tej samej wersji co raport. Dane prywatne nie powinny trafiać do nagrania, logów ani materiałów konkursowych.

## Publiczny odbiór demo

Po osobnym zleceniu udostępnienia wykonano [test przez publiczne HTTPS](evidence/public-demo.json), zakończony 3.10.2026 o 18:44:31 UTC. Nowy kontekst Chromium miał początkowo 0 ciasteczek; użyto zwykłego DNS i normalnej walidacji certyfikatu. Osiem grup objęło analizę syntetycznego konfliktu 45 minut, dwa warianty, dokładną kartę PDF, zapis i decyzję, próbę i obserwację, ICS, prywatną kopię/usunięcie/import oraz źródła katalogu. Testowe plany usunięto. Osobna sesja nie widziała zapisów. Cookie sesji miało Secure, HttpOnly i SameSite=Strict. Nie używano mocków.

Siedem skanów axe nie wykazało naruszeń. Przejścia 320/360 px i CSS 200% nie powodowały poziomego przepełnienia. Nie było błędów aplikacji ani nieoczekiwanych błędów konsoli. Oddzielnie odnotowano zablokowaną przez restrykcyjne CSP detekcję JS wstrzykniętą przez Cloudflare. Ten automatyczny wynik nie usuwa otwartych uwag częściowego audytu UX ani nie zastępuje badania czytnikiem ekranu.

[Próba restartu publicznego tunelu](evidence/public-recovery.json) potwierdziła rzeczywistą zmianę jego adresu i automatyczną rejestrację connectora. Stała domena odzyskała health po 7,38 s od żądania restartu. Nowa sesja następnie wykonała rzeczywistą analizę OPTIMAL, a `/materialy/` odpowiedziało 200. Nie restartowano aplikacji ani bazy. Architektura i zależność obliczeń od komputera operatora są w [PUBLIC_DEMO.md](PUBLIC_DEMO.md). Publiczne raporty są osobne od wcześniejszego lokalnego `verification.json` i nie zmieniają jego datowanego zakresu.

## Czego te dowody nie potwierdzają

Nie przeprowadzono badań z ludźmi, prawdziwego uzgadniania pracy ani pilotażu zatrudnienia. Nie potwierdzono zewnętrznego operatora, finansowania ani szyfrowania całego hosta. Publiczne demo i materiały udostępniono na osobne zlecenie użytkownika, ale ostateczne zgłoszenie konkursowe nie zostało zlecone ani wysłane. Publiczny test i pakiet PDF nie są potwierdzeniem przyjęcia zgłoszenia ani bezawaryjności hostingu. Syntetyczne 40 godzin pozostaje możliwością obliczoną, nigdy osiągniętym wpływem.
