# Utrzymanie Okna i przekazanie operatorowi

Autor materiału: DEFOZO SOFTWARE HOUSE, Michał Kiełtyka. Stan 2026-10-03. Nie zawarto partnerstwa ani umowy finansowania. Plan bezpłatnego dostępu dla użytkowniczek jest założeniem, a nie zobowiązaniem zewnętrznej organizacji.

## Odpowiedzialności przed pilotażem

| Rola | Obecna odpowiedzialność | Do uzgodnienia z operatorem |
| --- | --- | --- |
| Właściciel produktu | DEFOZO SOFTWARE HOUSE, Michał Kiełtyka | Organizacja rynku pracy, samorząd lub organizacja wspierająca powroty do pracy |
| Opiekun techniczny prototypu | Michał Kiełtyka | Dyżury, aktualizacje, dostęp do hosta, procedura awarii |
| Redaktor katalogu | Przegląd automatyczny i oznaczone źródła w repozytorium | Osoba zatwierdzająca dane, licencje, daty i budżet godzin redakcyjnych |
| Wsparcie i badania | Przygotowany protokół, bez rekrutacji | Osoba kontaktowa, zgody, minimalizacja danych, obsługa incydentów |

Przed rzeczywistymi danymi zatwierdzić operatora przetwarzania, treść informacji dla użytkowniczek, szyfrowanie dysków i kopii, dostęp administracyjny oraz finansowanie. Test kryptografii w kodzie nie dowodzi konfiguracji szyfrowania konkretnego dysku. Nie sprzedawać danych rodzin ani pozycji w rankingu.

## Źródła i ich odświeżanie

Codziennie sprawdzaj zmiany ofert, feedów GTFS i dat końca ważności. Rekord katalogu ma historię `draft`, `reviewed`, `published`, `stale`, `withdrawn`. Dwa odrębne kroki przeglądu i publikacji wykonuje polecenie operatora, poza publicznym API. Wykryta zmiana wymaga ponownego przeglądu, a wygasły rekord otrzymuje status `stale`. Samo pobranie nie przedłuża prywatnej zgody.

Każda wartość ma URL, datę i fragment potwierdzający. Godziny sekretariatu nie są godzinami opieki. Liczba miejsc nie jest przyjęciem konkretnej osoby. Cena nieznana pozostaje pusta. Nie publikuj syntetycznej dostępności pod nazwą realnej placówki. Przy awarii dostawcy działa formularz własnych danych i importer regułowy.

Wymagane źródła: [ZTP GTFS](https://gtfs.ztp.krakow.pl/), [OSM, prawa i licencja](https://www.openstreetmap.org/copyright), publiczne strony placówek wskazane w rekordach. OSM wymaga atrybucji i stosowania ODbL. Publiczny indeks GTFS sam w sobie nie rozstrzyga warunków redystrybucji. Przed publikacją kopii feedów lub grafu operator sprawdza warunki ZTP. Repozytorium przechowuje manifest i skrypty pobrania, a duże pliki danych pozostają wyłączone z wersjonowania.

## Import publicznych danych

`python -m api.importer --help` podaje aktualne podpolecenia. Importer wymaga HTTPS z dozwolonej domeny, sprawdza adres IP każdego przekierowania, przypina rozwiązany adres do połączenia TLS, ogranicza rozmiar i usuwa aktywny HTML. CSV/JSON przygotowuje operator. Groq/Firecrawl uruchamia się osobno z psst, wyłącznie dla publicznych źródeł. Sekretów nie przekazuje się do frontendu. Przed zwiększeniem liczby źródeł sprawdź regulamin, robots i obciążenie serwisu.

```powershell
python -m api.importer import-csv publiczne-rekordy.csv --out data/catalog/review-inbox
python -m api.importer validate-json data/catalog/review-inbox/identyfikator.json
python -m api.importer transition data/catalog/review-inbox/identyfikator.json reviewed --reviewer operator
python -m api.importer transition data/catalog/review-inbox/identyfikator.json published --reviewer operator
```

Po sprawdzeniu przenieś pojedynczy plik do `data/catalog/`. Pliki skrzynki `review-inbox` nie są widoczne w API. Wymagane kolumny CSV: `id,title,kind,source_url,fetched_at,terms`. Opcjonalne: `hours_start,hours_end,hours_excerpt,cost_grosze,cost_period,cost_excerpt,valid_from,valid_to`. Kwota oznacza całkowite grosze. Okres to `hour`, `day`, `month` albo `once` i musi występować w cytacie. Puste pola pozostają nieznane. Każdy rekord trafia do osobnego pliku w stanie `draft`, a importer nie nadpisuje istniejącego pliku. Przegląd obejmuje także zgodność fragmentu z aktualną stroną, której import CSV nie pobiera automatycznie.

Korpus ekstrakcji zawiera 67 publicznych przykładów z 36 URL oraz 35 syntetycznych testów trudnych przypadków. Sześć publicznych przykładów ma dodatnią etykietę godzin, dziewięć cenę wraz z okresem i składnikiem kosztu; 52 mają oba pola puste. Nowe źródła obejmują żłobki, kursy, uczelnie i urząd. Zawierają także rzeczywistą negację godzin, wyłączenie ceny dodatkowego pakietu, cenę przybliżoną i kilka przedziałów godzin. Cytaty są dokładnymi fragmentami pobranych stron, z datą i hash źródła. Etykiety powstały z pomocą asystenta AI przed ekstrakcją, bez niezależnego audytu człowieka.

Aktualny [wynik Groq i walidatora](../data/extraction/groq-benchmark.json) liczy odrzucenie i błąd jako porażkę; nie należy go zastępować dawnym 50/50. Pierwotny korpus oraz raport zachowano jako `public-pl-original50.json` i `groq-benchmark-original50.json`, kolejne przebiegi w `data/extraction/history/`. Zbiór nadal przeważa w kierunku brakujących danych o opiece. Nie jest reprezentatywnym oszacowaniem jakości polskich ofert i nie zastępuje redaktora. [Firecrawl](../data/extraction/live-firecrawl-result.json) pozostaje odrębnym testem pobrania strony.

Cena ma jawny składnik: pobyt/opieka, wyżywienie, wpisowe, opieka dodatkowa, kurs albo zakres nieustalony. Żadnego z nich nie należy traktować automatycznie jako pełnego kosztu. Przegląd katalogu ponownie sprawdza cytat, kwotę, okres i składnik. Rzeczywisty rekord KIDS SPACE Barska opisuje 500 zł jednorazowej opłaty rekrutacyjnej; nie podaje całego kosztu opieki ani ceny posiłków. Recenzentem zapisanym w historii jest asystent AI, nie członek zespołu jako domniemany niezależny audytor.

## Budżet utrzymania

Nie zakupiono hostingu i nie potwierdzono cen oferty. Arkusz kosztu operatora powinien obejmować poniższe wartości, z datą i źródłem cennika. Wykonany lokalnie test nie stanowi miesięcznej wyceny.

| Składnik | Sposób policzenia |
| --- | --- |
| API i baza | Stała cena hosta, dysku i ruchu, plus koszt aktualizacji |
| OTP | Host obsługujący zadeklarowaną pamięć, czas budowy grafu, transfer i kontrola jakości |
| Kopie | Zaszyfrowana pojemność, retencja i próby odtworzenia |
| Importy | Liczba stron i wywołań, aktualna taryfa, miesięczny limit |
| Redakcja i wsparcie | Rzeczywiste godziny pracy pomnożone przez uzgodnioną stawkę |
| Jedna ukończona analiza | Łączny koszt okresu podzielony przez ukończone analizy; osobno czas CPU i tras |

Nie sumuj samych tokenów jako kosztu produktu. Limity stron, wywołań i kosztu powinny blokować nowy import po wyczerpaniu budżetu. Zmierzone opóźnienia i limity analizy zapisuj wraz ze sprzętem i próbką.

## Incydenty i odtworzenie

W przypadku podejrzenia wycieku odłącz publiczny dostęp, zachowaj minimalne techniczne informacje bez treści planów, ogranicz uprawnienia oraz zmień właściwe sekrety w psst. Operator ustala osoby odpowiedzialne i obowiązki komunikacyjne przed pilotażem. Nie wpisuj do logów prywatnych requestów, identyfikatorów podopiecznych ani kluczy.

Planowana retencja to 30 dni bez aktywności i kopie do 7 dni. Uruchomiony serwis maintenance realizuje usuwanie według konfiguracji. Próba odtworzenia musi uwzględniać rejestr usunięć i nie odtwarzać skasowanych planów. Kopia JSON użytkowniczki importuje się jako nowy plan. Historyczne uzgodnienia wymagają ponownego potwierdzenia.

Przed przekazaniem: odtwórz czysty start według README, migracje, zapis i odczyt, eksport odbiorcy, import własnej kopii, usunięcie podczas analizy, odtworzenie po usunięciu, awarię OTP i importerów, a następnie sprawdź to przez docelowy HTTPS. Lokalny health nie potwierdza publicznego demo. Instrukcja tras: [infra/otp/README.md](../infra/otp/README.md).
