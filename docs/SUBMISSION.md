# Okno: wykonalny plan pracy i opieki

DEFOZO SOFTWARE HOUSE · Michał Kiełtyka · ImpactHER: Technology for Real Change · New Idea.

## Problem i wartość

Praca kończy się o 17:00. Opieka też. Sama oferta pracy nie rozwiązuje problemu powrotu do zatrudnienia, gdy trzeba jeszcze dojechać i odebrać dziecko. Okno pomaga wskazać konkretne godziny i warunki, które użytkowniczka może uzgodnić z pracodawcą lub opiekunem.

Użytkowniczka podaje grafik, zasoby opieki, dojazdy, daty i granice budżetu. Aplikacja pokazuje konflikt, oblicza dopuszczalne warianty i porównuje ich koszt, zapas czasu oraz zachowany wymiar pracy. Karta dla pracodawcy zawiera proponowane godziny i okres próby, bez informacji o rodzinie, placówkach i prywatnych kosztach.

W syntetycznym przykładzie praca 09:00–17:00 daje 45 minut kolizji z opieką. Zmiana na 08:15–16:15 usuwa konflikt, a 08:00–16:00 daje 15 minut zapasu. Oba warianty zachowują 40 godzin pracy tygodniowo i wymagają uzgodnienia. Kontrpropozycja 08:30–16:30 pozostawia 15 minut kolizji, którą aplikacja wykrywa przy ponownym przeliczeniu.

## Od wariantu do próby

Odpowiedź, odmowę lub kontrpropozycję można zapisać i ponownie sprawdzić. Po potwierdzeniu zależności aplikacja prowadzi przez okres odniesienia, próbę oraz zapis rzeczywistej pracy, kosztów i wysiłku organizacyjnego. Obliczony plan i rzeczywisty rezultat pozostają odrębnymi informacjami.

## Technologia

OR-Tools CP-SAT oblicza warianty, a niezależny walidator kontroluje harmonogram. Opcjonalny OpenTripPlanner korzysta z OSM i GTFS; dostępne są także własne czasy podróży. Zapisane plany są szyfrowane, a eksport obejmuje tylko zatwierdzone pola. Publiczny katalog podaje źródła i daty. Opcjonalna ekstrakcja AI dotyczy wyłącznie publicznych materiałów.

[Instrukcja demo](jury/README.md) · [Materiały](MATERIALS.md) · [Architektura](ARCHITECTURE.md) · [Testy](VALIDATION.md) · [Uruchomienie](../README.md).
