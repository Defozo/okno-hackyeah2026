# Audyt UX aktualizacji pitchu

Cykl: `f609b2dd-4e95-4a58-a92a-fd09ebadb0e8`. Model niezależnego audytora: `gpt-6-astra`.

## Zakres

Zmiany należą do zakończonego zadania: sześć ekranów w `web/src/{App,Editor,Results,Agreements,Trial,Catalog}.tsx` i strona materiałów w `public-demo/worker/index.js`. Kopie źródeł, zależności oraz kadry filmu wykryte przez hook nie są odrębnymi ekranami aplikacji.

Podgląd pod `http://127.0.0.1:18435/` łączy rzeczywisty lokalny frontend/API i worker materiałów. Korzysta z testowego stosu `okno`, odrębnego od publicznego `okno-demo`, z własną bazą i woluminem. Audytor ma nową przeglądarkę oraz może używać wyłącznie danych testowych. Trasa `__preview-unavailable` pokazuje rzeczywisty komunikat workera przy braku połączenia. Przegląd nie wymaga wdrożenia produkcyjnego.

## Pierwszy niezależny przegląd

[Raport](evidence/ux-pitch-audit-initial.json): **partial**, zero zgłoszonych usterek, 39 zakończonych operacji przeglądarki. Wszystkie trzy adresy sprawdzone. Cel i pierwszy krok były zrozumiałe. Pokrycie nie obejmowało całej ścieżki uzgodnień i próby. Próba edycji dat nie dała jednoznacznego wyniku, więc nie jest dowodem błędu produktu. Audytor nie otrzymał historii, pamięci, źródeł, tego planu ani wcześniejszych raportów.

## Plan przed pierwszą rundą zmian

1. **Potwierdzona poprawka:** katalog po filtrowaniu z dwóch rekordów do zera nie aktualizuje żadnego regionu live. Obecny `Catalog.tsx` należy do zmienianego zakresu. [Osobna reprodukcja](evidence/ux-pitch-catalog-confirmation.json) potwierdza widoczny pusty wynik, pozostawiony fokus i brak ogłoszenia. Dodać trwały region `status` z liczbą wyników oraz komunikatem ładowania. Nie zmieniać wyszukiwarki, źródeł ani znaczenia danych.
2. **Hipoteza do sprawdzenia:** edycja dat. Powtórzyć istniejącą reprodukcję zwykłego wpisania i obsługi klawiaturą. Nie zmieniać dat ani walidacji bez odtworzonego błędu.
   Reprodukcja [dwoma sposobami](evidence/ux-pitch-date-confirmation.json) nie odtworzyła błędu wartości ani żądania. Potwierdziła natomiast, że widoczny błąd kolejności dat z walidacji formularza nie ustawia `aria-invalid` ani powiązania opisu na polu daty końca. W tej samej pierwszej rundzie ujednolicić semantykę komunikatu z już obsługiwanymi błędami API, zachowując walidację i wartość daty. Sprawdzić ustawienie oraz usunięcie atrybutów po poprawieniu daty.
3. **Bez zmiany produktu:** brak odnośnika do materiałów w menu aplikacji nie jest potwierdzonym wymaganiem; jury otrzymuje bezpośredni adres materiałów. Zachować istniejącą nawigację.
4. **Akceptacja:** build, rzeczywiste filtrowanie 2 → 0 → 2 z aktualizacją regionu status, zachowany fokus, istniejący pełny test przeglądarkowy i axe. Następnie świeży niezależny audyt z identycznym minimalnym requestem i nowym raportem, bez udostępniania tego dokumentu. Maksymalnie dwie rundy poprawek.

Przed poprawką pełny test lokalnego podglądu przeszedł dziewięć grup przepływów i osiem skanów axe, widoki 320/360 px oraz CSS 200%. To osobny dowód techniczny; nie uzupełnia automatycznie pokrycia niezależnego audytora.

## Drugi przegląd i plan drugiej rundy

[Świeży drugi audyt](evidence/ux-pitch-audit-intermediate.json): **partial**, 81 operacji przeglądarki. Potwierdził aktualizację statusu katalogu oraz semantykę błędnego pola. Nie otrzymał poprzedniego raportu ani planu. Fingerprint źródeł nie zmienił się w trakcie przeglądu.

Potwierdzone UX-01: komunikat po analizie pustego planu zachęcał do porównywania nieistniejących wariantów. W drugiej, ostatniej rundzie dopasować status do rzeczywistego wyniku: przy pustym okresie poprosić o dodanie zajęć, przy brakach o uzupełnienie danych, przy braku rozwiązania lub rozstrzygnięcia wskazać właściwy wynik. Zachętę do porównywania wyświetlać tylko, gdy istnieją warianty. Zachować dane i wszystkie przejścia do formularza.

Akceptacja: rzeczywista analiza pustego planu, powrót do formularza bez utraty własnej nazwy, rzeczywisty przykład z wariantami oraz istniejące regresje pozostałych statusów. Build i test przeglądarkowy po zmianie. Potem ostatni świeży audyt z tym samym minimalnym requestem, bez trzeciej rundy zmian.

Przegląd zmienionych komponentów według checklisty React: komunikat analizy jest czystą funkcją poza komponentem; błąd daty jest wyprowadzany podczas renderowania, bez dodatkowego efektu lub kopii stanu; status katalogu zachowuje węzeł DOM; nie dodano zależności, subskrypcji ani wywołań sieciowych. TypeScript i produkcyjny build przeszły. Pełna kontrola przeglądarkowa po drugiej zmianie ponownie przeszła dziewięć grup przepływów oraz osiem skanów axe.

## Końcowy niezależny przegląd

[Trzeci, końcowy raport](evidence/ux-pitch-audit-final.json): **partial**, zero nowych usterek, 51 operacji przeglądarki. Audytor pracował w nowej sesji z wyłączoną pamięcią i instrukcjami projektu. Ocenił pierwsze wrażenie przed eksploracją. Fingerprint źródeł był identyczny przed przeglądem i po nim.

Potwierdził komunikat pustego planu, dwa warianty rzeczywistego przykładu oraz aktualizację regionu status katalogu. Sprawdził także menu mobilne, przywracanie fokusu i stronę materiałów. [Regresja statusów](evidence/ux-pitch-status-verification.json) obejmuje rzeczywiste analizy pustego planu i przykładu oraz jawnie oznaczone symulacje pozostałych odpowiedzi. Końcowy bundle aplikacji: `index-GtiVDxWa.js`.

Wykorzystano dwie dozwolone rundy poprawek. Nie wykonywano trzeciej. Ocena niezależna była próbkowa: nie obejmowała całej ścieżki zapisu, uzgodnień i próby, rzeczywistego powiększenia 200% ani odsłuchu czytnikiem ekranu. Osobne testy automatyczne zachowują własny zakres i nie oznaczają pełnej zgodności z WCAG. Raporty wcześniejszych cykli pozostają zachowane jako historyczne.

## Publikacja sprawdzonej wersji

Po zakończeniu przeglądu wdrożono ten sam obraz `okno-app:ux-pitch-20261003`, SHA-256 `e352da934299af70618da680118663543b5b7a04df3bbd01228cbbca82b27910`, do wydzielonego publicznego stosu. Brama Sites pozostała w wersji 4. [Test publiczny](evidence/public-demo.json), zakończony 3 października 2026 o 22:14:28 UTC, przeszedł osiem przepływów, siedem skanów axe bez naruszeń, wąskie widoki i CSS 200%. Nowa sesja zaczynała z zerem cookies. Sprawdzono zapis, izolację, decyzję, próbę, PDF, ICS, kopię, import i usunięcie własnych danych syntetycznych. Nie było błędów aplikacji; raport oddzielnie zachowuje blokadę skryptu Cloudflare przez CSP.

Źródła tej wersji i zgodność publicznego repozytorium potwierdza [raport publikacji kodu](evidence/public-source.json). Prezentacja i nagranie zachowują wcześniej sprawdzone pliki. Aktualizacja dotyczy komunikatów i dostępności formularza, nie przedstawionego w filmie przepływu z wariantami.

[Docelowa kontrola trzech poprawek przez publiczne HTTPS](evidence/ux-pitch-public-verification.json), zakończona o 22:20:47 UTC, także przeszła. Nowa sesja potwierdziła właściwy komunikat pustego planu i zachowanie nazwy, trwały status katalogu 2 → 0 → 2 z zachowaniem fokusu oraz powiązany błąd nieprawidłowej daty bez wysłania analizy. Nie użyto mocków ani zapisu planu. Dwie wcześniejsze próby przerwane przez zbyt ścisłe założenia skryptu zachowano w raporcie jako błędy testu, nie produktu.
