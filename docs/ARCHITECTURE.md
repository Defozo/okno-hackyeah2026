# Architektura Okna

## Przepływ danych

React, TypeScript, React Hook Form i Zod obsługują formularz warunków pracy, opieki, podróży oraz dat. FastAPI/Pydantic waliduje żądanie. OR-Tools CP-SAT oblicza harmonogram i warianty, a niezależny walidator sprawdza wynik przed prezentacją. Solver działa w osobnym procesie z limitem czasu i ograniczoną pulą zadań.

Podstawowy profil używa zadeklarowanych czasów podróży. Opcjonalny adapter OpenTripPlanner przelicza kierunek, datę i godzinę przejazdu na grafie OSM/GTFS. Nie zastępuje brakującej trasy wymyślonym czasem.

## Co oznacza wynik

`OPTIMAL` dotyczy wprowadzonych dat, zasobów, kolejności miejsc i dozwolonej siatki godzin. `FEASIBLE` oznacza znaleziony wariant bez pełnego dowodu optimum. `INFEASIBLE` dotyczy sprawdzonej domeny modelu; `UNKNOWN`, niekompletne dane i wygasłe źródła są prezentowane oddzielnie. Jedna analiza obejmuje do 731 dni i 60 000 kandydatów. Szczegółowy [kontrakt obliczeń](../api/solver/README.md) opisuje czas, koszty, przekazania i ograniczenia.

Zmiana warunków wymaga nowej analizy. Odmowa wyklucza konkretną propozycję godzin; kontrpropozycję przelicza się ponownie. Potwierdzenie oznacza ustalenie zapisane przez użytkowniczkę, nie uwierzytelnioną decyzję pracodawcy ani rezerwację miejsca opieki.

## Zapis i eksport

Trwały zapis jest oddzielony od analizy. SQLAlchemy i Alembic obsługują PostgreSQL w Compose oraz SQLite w testach i lokalnym rozwoju. Plany, migawki eksportów i historia operacji są szyfrowane Fernet. Kontrola wersji i idempotencja chronią przed nieaktualną edycją oraz powtórzeniem żądania.

Sesja przeglądarki określa dostęp do zapisów. Utrata cookie oznacza utratę dostępu do planów tej sesji. Własny eksport JSON można zaimportować jako nowy plan; historyczne zgody wymagają ponownej oceny. Użytkowniczka może usunąć plan.

Podgląd karty jest związany z wersją planu i listą zatwierdzonych pól. Karta pracodawcy pomija dane rodziny, nazwy placówek i prywatne wydatki. Playwright generuje PDF, a `icalendar` kalendarz ICS. Eksport nie wysyła wiadomości ani nie potwierdza zgody odbiorcy.

## Próba i obserwacje

Po obliczeniu planu i potwierdzeniu zależności użytkowniczka zapisuje okres odniesienia, rozpoczyna próbę i dodaje obserwacje pracy, kosztów oraz wysiłku organizacyjnego. Brak obserwacji pozostaje brakiem danych. Zmiana warunków blokuje bieżącą gotowość i zachowuje historię. Obliczone 40 godzin w przykładzie nie jest wynikiem rzeczywistej próby zatrudnienia.

## Prywatność i import

Prywatne grafiki trafiają do własnego API i nie są przesyłane do usług AI. Importer działa poza publicznym API i odczytuje publiczne źródła. Pole wymaga pochodzenia, cytatu i przeglądu przed publikacją. Wsparcie Groq/Firecrawl jest opcjonalne. [Utrzymanie](OPERATIONS.md) opisuje role, retencję, kopie i przegląd katalogu.
