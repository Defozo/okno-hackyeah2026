# Plan korekt UX

Cykl: 16c80f28-5ee9-4b6b-bdcd-80fe5888ef09. Źródło: niezależny audit-1-retry.json. Runda poprawek: 1 z maksymalnie 2.

Zmiany dotyczą zakończonej implementacji Okna. Aplikacja jest lokalnym podglądem testowym, a audyt używa nowej sesji i danych syntetycznych. Pierwszy launcher nie znalazł Codexa; po skorygowaniu PATH wyłącznie dla procesu niezależny audyt wykonał 81 operacji przeglądarki.

## Przyjęte ustalenia

- F1: zamknięte menu mobilne pozostaje osiągalne Tab i w drzewie dostępności. Wyłączyć jego zawartość z interakcji i semantyki, gdy jest schowane; przy otwarciu zapewnić wejście fokusu, a przy zamknięciu powrót do przycisku. Zachować wszystkie pozycje oraz nawigację desktopową.
- F2: błędna lista dat ujawnia techniczną ścieżkę i komunikat po angielsku. Dodać polski opis wskazujący ofertę/pole, aria-invalid, aria-describedby i możliwość przejścia do błędnego pola. Poprawienie danych ma umożliwić ponowną analizę bez utraty formularza. Zachować walidację serwera i wszystkie ograniczenia.
- F3: interfejs utożsamia każdy UNKNOWN z limitem analizy. Silnik dla pustego okresu zwraca needs_input i empty_period. W interfejsie nadać brakowi danych pierwszeństwo i skierować do formularza; informację o limicie wyświetlać na podstawie rzeczywistej przyczyny. Nie zmieniać stanów ani reguł solvera.

## Decyzje i granice

Nie wymagają decyzji produktowej: są to potwierdzone błędy dostępności i opisu istniejących stanów. Zachować pełny zakres ofert, opieki, tras i dat, status propozycji, braki, zgody, oddzielny zapis, prywatność eksportu i historię prób. Nie zmieniać zakresu produktu ani danych syntetycznych w rzeczywiste deklaracje.

Ograniczenia audytu: nie ukończył zapisu i próby, importu/eksportu, błędów sieciowych ani rzeczywistego zoomu. Istniejące testy tych przepływów są osobnymi dowodami. Świeży audyt ma otrzymać ten sam minimalny request, bez tego planu i raportu.

## Odbiór

1. Przy 390 px zamknięte menu nie ma punktów tabulacji ani dostępnych ukrytych kontrolek; otwarcie i Escape działają z przewidywalnym fokusem. Sprawdzić także desktop.
2. Własna oferta z datą 2026-99-99 dostaje polski błąd powiązany z polem; po poprawieniu data i pozostałe dane pozostają, a analiza działa.
3. Pusty plan wskazuje dodanie oferty/danych bez komunikatu o limicie i bez bezcelowego ponawiania. Rzeczywiste timeout/UNKNOWN pozostają odróżnione od braków.
4. Build TypeScript/Vite oraz dotychczasowe przepływy przeglądarkowe, axe i klawiatura po zmianach.
5. Świeży niezależny audyt tą samą procedurą. Ewentualna druga runda tylko dla potwierdzonych uwag; żadnej trzeciej rundy.
6. Po końcowym podglądzie zaktualizować dowody i pakiet PDF/ZIP, jeśli zmienione materiały przestały odpowiadać interfejsowi. Zakończyć dokładnie bieżący cykl poleceniem complete, z uczciwym statusem pokrycia.

Doprecyzowanie F2 przed końcem pierwszej rundy: kontrolowane pole listy dat usuwało końcowy separator przy każdym znaku (splitDates + join), przez co wpisanie drugiej daty klawiaturą było niemożliwe. Zachować surowy tekst podczas wpisywania, normalizować po opuszczeniu pola i sprawdzić wpisanie dwóch dat klawiaturą oraz reset zewnętrzny. To naprawa edytowanego pola, bez zmiany zakresu kalendarza.

Uzupełnienie przed końcem pierwszej rundy, na podstawie wykonanych regresji: axe potwierdził kontrast nieaktywnych dni tygodnia 3,9:1 (tekst 11px), więc przyciemnić tekst bez zmiany stanu. Równoległe próby osiągnęły prawidłowy limit API 429, ale błąd zapisu jest widoczny tylko pod zasłoną modala. Zachować limit i zgodę; pokazać błąd jako dostępny alert wewnątrz modala, utrzymać możliwość ponowienia, sprawdzić zasymulowane 429 i następujący skuteczny zapis. Kolejny test klawiatury wykonać bez konkurujących obliczeń.

Ta sama potwierdzona ścieżka błędu dotyczy dialogu odpowiedzi w Agreements (catch przekazywał błąd wyłącznie do tła App). Objąć go widocznym lokalnym alertem, fokusem i zachowaniem wpisanej odpowiedzi. Test głównego przepływu wstrzyknie raz 429, a ponowienie wykona przez rzeczywiste API.

Odbiór rundy 1: build TypeScript/Vite zakończony kodem0. Obraz dfba7729a471f2348668dff547bdbc56fa57e8e42989dc76e0d1bc73901b2a23; 28 plików uruchomienia zgodnych z katalogiem. Główny browser: 9 grup przepływów, 8 ekranów axe bez naruszeń, retry decyzji po kontrolowanym429 zakończony rzeczywistym200. Klawiatura: oferta/analiza/zapis/usunięcie passed. UXregression: 5 ekranów axe bez naruszeń, menu390 i breakpointy, dwie daty znak po znaku, realAPI pustego i poprawionego planu, 7 jawnych mocków stanów, alert zapisu429 i rzeczywisty retry200, usunięcie własnego planu. Kontrolowane429 są opisane osobno od błędów niespodziewanych. Backend i limity bez zmian. Uruchomiono świeży audit-2.json z niezmienionym requestem; audytor nie otrzymuje planu ani poprzedniego raportu.

## Runda poprawek 2 z 2

Świeży audit-2.json: partial z dwoma nowymi ustaleniami. Potwierdzono poprawę menu i pustego planu. Przyjmujemy:

- F1: wartość -1 w wymaganym płatnym czasie pracy daje ogólny komunikat, bez nazwy/minimum/odnośnika do pola. Powiązać istniejącą regułę minimum0 z polem: polski opis, aria-invalid/describedby, odnośnik i fokus, usuwanie błędu po poprawie. Nie zmieniać minimum ani jednostki godzin, nie ukrywać walidacji serwera. Podsumowanie nie może obiecywać odnośników, gdy ich nie zawiera.
- F2: angielskie etykiety miejsc i podopiecznego w syntetycznych przykładach utrudniają zrozumienie. Spójnie przetłumaczyć wyłącznie etykiety nowo otwieranych przykładów w interfejsie, zachowując wszystkie odniesienia miejsca/podopiecznego oraz identyfikatory biznesowe i enumy. Nie zmieniać własnych danych, zapisanych planów, materiałów źródłowych ani przypiętej referencji benchmarku. Sprawdzić równość wyniku analizy oraz zachowanie powiązań.

Odbiór: -1 wskazuje wymagany czas pracy i minimum0; odnośnik przenosi fokus; poprawienie na0 usuwa błąd i pozwala na analizę. Przykład pokazuje polskie nazwy w ofercie, opiece i dojazdach; wynik, koszty, godziny i ograniczenia pozostają takie same. Powtórzyć build, odpowiednie regresje i świeży niezależny audyt z tym samym minimalnym requestem. Po audycie3 nie wykonywać trzeciej rundy; uczciwie zapisać ewentualne pozostałe ustalenia i ograniczenia pokrycia.

Odbiór rundy2: build TypeScript/Vite poprawny. Obraz a71bdc315b13c752515cece6b976ce66094601471c7391ab748b55b97b6b7762, frontend index-CUhktpe1.js / index-3KQfrRp2.css, 28 zgodnych plików uruchomienia. Pełny zestaw 232 testów passed w29,62s (1 ostrzeżenie Starlette). Mainbrowser 9 grup/8 axe, klawiatura oferta/zapis/usunięcie passed. UXregression passed: 4 rzeczywiste analizy, 7 jawnych mocków, 5 axe bez naruszeń; ujemne godziny/budżet i poprawa0/null; polskie etykiety z równoważnym wynikiem OPTIMAL, oboma harmonogramami, konfliktami, metrykami i etapami dowodu. Osobny raport offline obejmuje3 przykłady, brak modyfikacji źródeł i kolizje nazw. Naprawiono wyłącznie klienta testowego po błędzie localhost/IPv6 oraz asercję synonimu komunikatu budżetu, bez dodatkowej zmiany UI. Wszystkie plany testowe używane przez regresje usunięto. Uruchomiono audit-3.json z niezmienionym requestem. To końcowy niezależny audyt po dwóch rundach.

## Końcowy audyt i rozstrzygnięcie

Świeży audit-3.json zakończył się statusem partial i dwoma nowymi ustaleniami. Zachowujemy jego pełną, niezmienioną treść. Audyt wykonał niezależny asystent AI w czystej przeglądarce; nie jest to badanie z udziałem człowieka ani potwierdzenie pełnej zgodności WCAG.

- F1, daty: zgłoszenia analizy starego zakresu i cofnięcia daty nie odtworzono w dwóch udokumentowanych metodach (fill oraz klawiatura z natywnymi zdarzeniami), po potwierdzonym rzeczywistym blur. Data 2026-10-01 pozostała wpisana, pojawił się błąd zakresu, przycisk był wyłączony i nie wysłano żądania API. Po opuszczeniu formularza i powrocie data nadal wynosiła 01; lokalny błąd zniknął, a przycisk ponownie się uaktywnił. W tym stanie nie wykonywano kolejnej próby błędnego zakresu. Osobny przegląd kodu potwierdza walidację przed żądaniem solve. Dwie kontrole dodatnie ze zmienioną poprawną datą 08 wysłały faktyczny zakres 05..08 i otrzymały HTTP200 z tym samym checked_period. Rozbieżność z audytorem pozostaje niewyjaśniona; nie twierdzimy, że zgłoszenie zostało uniwersalnie wykluczone. Brak aria-invalid/describedby przy błędzie zakresu został zaobserwowany, ale treść błędu znajduje się w etykiecie i dostępnej nazwie pola. Nie wykonano odsłuchu czytnikiem ekranu.
- F2, katalog: potwierdzona otwarta wada dostępności. Filtr zmienia 2 rekordy na 0 i pokazuje „Nie ma pasujących źródeł”, lecz nie ogłasza zmiany przez role=status/aria-live. Obecny live region nadal zawiera wcześniejszy komunikat analizy. Pozostawić jako zadanie do naprawy, bez deklaracji pełnego odbioru UX.

Dowód dodatkowej kontroli: docs/evidence/ux-final-findings.json, zakończony 2026-10-03T17:01:17.853Z, bundle index-CUhktpe1.js, brak błędów JavaScript. Jest to odrębna weryfikacja wskazanych ustaleń, nie czwarty niezależny audyt. Nie zmieniano interfejsu.

Wykorzystano obie dozwolone rundy poprawek. Punkt6 workflow.md zabrania trzeciej rundy po końcowym audycie. Kończymy cykl statusem partial. Nieukończone przez audytora przepływy zapisu/importu/eksportu mają osobne dowody z testów głównych, lecz nie rozszerzają pokrycia samego audytu. Pozostają niewykonane: badanie z ludźmi, odsłuch czytnikiem, fizyczny telefon i natywny zoom200%. Aktualizujemy dokumentację, PDF i ZIP z danymi TEAM.json oraz jawnymi ograniczeniami; nie publikujemy ani nie wysyłamy zgłoszenia.
