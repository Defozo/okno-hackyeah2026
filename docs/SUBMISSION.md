# Okno: wykonalny plan pracy i opieki

**DEFOZO SOFTWARE HOUSE**. Autor i jedyny członek zespołu: **Michał Kiełtyka**. Kategoria: **ImpactHER: Technology for Real Change**. Etap: **New Idea**.

## Problem

Praca kończy się o 17:00. Opieka też. Samo znalezienie oferty nie rozwiązuje problemu powrotu do pracy, jeśli po drodze trzeba jeszcze dojechać i odebrać dziecko. Kobieta potrzebuje konkretnych godzin i warunków, z którymi może wrócić do rozmowy z pracodawcą.

## Rozwiązanie

Okno zamienia grafik pracy, opiekę i dojazdy w plan do uzgodnienia. Wskazuje konflikt, oblicza dopuszczalne zmiany i pokazuje ich koszt, zapas czasu oraz zachowany wymiar pracy. Użytkowniczka ustala granice, których plan ma przestrzegać.

W przykładzie demonstracyjnym praca 09:00–17:00 oznacza odbiór 45 minut po zamknięciu placówki. Przesunięcie pracy na 08:15–16:15 usuwa tę kolizję. Wariant 08:00–16:00 daje dodatkowe 15 minut zapasu. Oba zachowują 40 godzin płatnej pracy w tygodniu i wymagają uzgodnienia godzin z pracodawcą.

Wybrany wariant trafia do karty dla pracodawcy z godzinami i okresem próby. Użytkowniczka kontroluje jej treść przed eksportem. Karta pomija dane rodziny, placówek i prywatne koszty. Odpowiedź lub kontrpropozycję można zapisać i ponownie przeliczyć plan. Po uzgodnieniu warunków aplikacja prowadzi przez próbę i porównanie rzeczywistego czasu pracy, kosztów oraz wysiłku organizacyjnego.

## Działający produkt

Demo obejmuje cały przepływ: od własnych warunków, przez analizę i uzgodnienia, do próby, eksportu PDF i kalendarza oraz usunięcia zapisanego planu. Model OR-Tools CP-SAT uwzględnia daty, kilku podopiecznych, pojemność opiekunów, kierunki dojazdu, przekazania, wyjątki i budżet. Niezależny walidator sprawdza wynik. Routing OpenTripPlanner na danych OSM i GTFS dla Krakowa przelicza dojazdy po zmianie godzin; można także wpisać czasy ręcznie.

Publiczny katalog pozwala sprawdzić źródło i datę informacji o opiece. Opcjonalny import AI pomaga odczytać publiczne materiały. Prywatne grafiki nie trafiają do modelu językowego. Przykład w filmie i demo jest syntetyczny.

## Następny krok

Planowany pilotaż z organizacją wspierającą powrót kobiet do pracy sprawdzi, czy obliczone warianty prowadzą do uzgodnień i utrzymania zatrudnienia. Pomiar obejmie godziny płatnej pracy, koszt opieki i dojazdu oraz czas poświęcony na organizację. Protokół badań i definicje miar są przygotowane w [RESEARCH.md](RESEARCH.md).

## Materiały

- [Interaktywne demo](https://okno-impacther-2026.defozo.chatgpt.site/) i [strona materiałów](https://okno-impacther-2026.defozo.chatgpt.site/materialy/).
- [Prezentacja PDF](https://okno-impacther-2026.defozo.chatgpt.site/materialy/prezentacja.pdf), [edytowalny PPTX z notatkami](https://okno-impacther-2026.defozo.chatgpt.site/materialy/prezentacja.pptx) i [film z polskim lektorem](https://okno-impacther-2026.defozo.chatgpt.site/materialy/demo.mp4).
- [Instrukcja jurora](jury/README.md), [kryteria i źródła wymagań](jury/REQUIREMENTS.md), [wyniki kontroli technicznych](VALIDATION.md), [uruchomienie](../README.md).

## Autorstwo i zasoby

Michał Kiełtyka odpowiada za projekt jako jedyny członek DEFOZO SOFTWARE HOUSE. Istotnie wykorzystano Codex do koncepcji, programowania, testów, interfejsu i materiałów. Film korzysta z syntetycznego lektora ElevenLabs oraz oryginalnego podkładu instrumentalnego. Szczegóły: [AI_USAGE.md](../AI_USAGE.md), [THIRD_PARTY.md](../THIRD_PARTY.md), [PREEXISTING.md](../PREEXISTING.md).

Istniejące zgłoszenie HackTribe pozostaje na etapie **New Idea**. Bieżące zlecenie obejmuje zapis materiałów i opisu przy zachowaniu widoczności wpisu. Wynik zapisu i ponownego odczytu dokumentuje `HACKTRIBE_UPDATE_RESULT.json`. Osobna finalizacja konkursowa nie jest objęta tym zleceniem.
