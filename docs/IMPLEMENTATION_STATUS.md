# Okno: zakres implementacji i granice ukończenia

Zespół: **DEFOZO SOFTWARE HOUSE**. Jedyny członek: **Michał Kiełtyka**. Dane pochodzą z [TEAM.json](../TEAM.json). Stan dokumentu: 2026-10-03.

Dokument mapuje wybrany [official-2026-10-03/PLAN.md](../official-2026-10-03/PLAN.md), a nie historyczny plan z katalogu głównego. Zaimplementowano techniczną ścieżkę od własnego grafiku do analizy, karty odbiorcy, decyzji, próby i obserwacji. Uruchomienie, testy automatyczne i przykłady nie stanowią badania skuteczności społecznej. Dokładny zakres wykonanych przebiegów rozstrzygają datowane raporty wskazane w [VALIDATION.md](VALIDATION.md).

## Mapa wymagań planu

| Sekcja planu | Realizacja i pliki | Dowód lub granica |
| --- | --- | --- |
| 1. Decyzja i wartość | [Editor](../web/src/Editor.tsx), [Results](../web/src/Results.tsx), [Agreements](../web/src/Agreements.tsx), [Trial](../web/src/Trial.tsx) prowadzą od konkretnej oferty do obserwacji rezultatu | Techniczny przepływ jest dostępny. Hipoteza popytu i wpływu wymaga badań |
| 2. Wykorzystanie propozycji | Model ograniczeń, kierunkowe trasy, własne oferty, listy działań, osobne karty i backup | Wybrany wariant D z elementami A/B/C. Brak modułów CV i sejfu cyberprzemocy jest zgodny z wyborem planu |
| 3. Wymagania jury | [SUBMISSION.md](SUBMISSION.md), [SPEAKER_NOTES.md](SPEAKER_NOTES.md), [prezentacja PDF](../output/pdf/okno-impacther.pdf), [COMPARISON.md](COMPARISON.md) | Materiały podpisano danymi zespołu. Zapis plików nie oznacza zgłoszenia |
| 4. Odbiorczynie i potrzeba | [RESEARCH.md](RESEARCH.md), [pilot-template.json](pilot-template.json), źródło EIGE w [SOURCES.md](../SOURCES.md) | 0 wywiadów, 0 sesji użyteczności z osobami spoza zespołu, 0 rzeczywistych prób zatrudnienia |
| 5. Pełna ścieżka | [App](../web/src/App.tsx), edytor godzin, opieki, podróży i granic; warianty, zgody/odmowy/kontrpropozycje, backup i usunięcie; [API](../api/main.py) | [Testy API](../tests/test_api.py) oraz zapisany [przebieg przeglądarkowy](evidence/browser-report.json). Odmowa i brak wyniku nie kończą się fikcyjnym sukcesem |
| 6. Dane i stany | [domain.py](../api/domain.py), [contracts.py](../api/contracts.py), [plans.py](../api/plans.py), migracje bazy | Rozdzielono status solvera, kompletność danych, ustalenia i obserwacje. Historia zgód oraz prób pozostaje zachowana |
| 7. Silnik wykonalności | [engine.py](../api/solver/engine.py), [time.py](../api/solver/time.py), [niezależny walidator](../api/validation/schedule.py), [CareChains](../web/src/CareChains.tsx) | Pełne daty w zadanej domenie, osobne pieniądze i czas, pojemność, odpoczynek z podróżą, wymagany kurs, jawne przekazania i opieka także bez pracy; [test_solver.py](../tests/test_solver.py) |
| 8. Transport, katalog i AI | [routes.py](../api/routes.py), [transit.py](../api/transit.py), [RoutePlanner](../web/src/RoutePlanner.tsx), [Catalog](../web/src/Catalog.tsx), [catalog.py](../api/catalog.py), [importer.py](../api/importer.py) | OTP zweryfikowano na rzeczywistym grafie. Formularz zachowuje własne dane. Katalog rozdziela verified/synthetic/all. AI dotyczy wyłącznie publicznych materiałów |
| 9. Interfejs | [styles.css](../web/src/styles.css), Radix Tabs/Dialog, pola React Hook Form/Zod, czytelne statusy, pełna tabela harmonogramu, porównanie pracy przed/po | Przebieg przeglądarki, klawiatura i [regresje UX](evidence/ux-regression.json) sprawdzają responsywność, axe, menu mobilne, błędy dat i ponowienia w dialogach. Osobny audyt AI ma własny zakres w [VALIDATION.md](VALIDATION.md). Brak badania czytnikiem ekranu i z użytkowniczkami |
| 10. Architektura i API | [FastAPI](../api/main.py), [worker.py](../api/worker.py), [api.generated.ts](../web/src/api.generated.ts), [klient](../web/src/api.ts), [compose.yaml](../compose.yaml) | Solver pracuje w osobnym procesie, limit całej analizy i ograniczona pula. Idempotencja, kontrola wersji i ignorowanie spóźnionych odpowiedzi w interfejsie |
| 11. Prywatność i eksport | [security.py](../api/security.py), [database.py](../api/database.py), [exports.py](../api/exports.py), [maintenance.py](../api/maintenance.py) | Lista dozwolonych pól, związany z wersją podgląd, PDF/HTML/tekst/ICS, własny JSON, CSRF, sesja właściciela, szyfrowanie danych w bazie i kopii. Konfiguracja konkretnego hosta wymaga osobnego odbioru |
| 12. Uruchomienie i utrzymanie | [README](../README.md), [OPERATIONS.md](OPERATIONS.md), [PUBLIC_DEMO.md](PUBLIC_DEMO.md), [instrukcja OTP](../infra/otp/README.md) | Profile core/transit, sekrety psst, rozdzielone role bazy. Publiczny przepływ HTTPS i odzyskanie połączenia po restarcie tunelu przeszły test. Obliczenia zależą od komputera operatora i łącza; operator pilotażu i jego finansowanie pozostają nieuzgodnione |
| 13. Etapy i odbiór | Niniejsza mapa oraz [VALIDATION.md](VALIDATION.md) | Techniczną implementację oceniają testy i raporty. Badanie potrzeby, pilotaż i publiczne wdrożenie pozostają osobnymi czynnościami |
| 14. Testy i jakość | [tests](../tests/), [browser-check.cjs](../scripts/browser-check.cjs), [benchmark](../data/synthetic/benchmark.py) | Zestaw pokrywa poprawność, stany awarii, źródła, transport, dostęp i eksport. Wynik oraz ograniczenia każdego przebiegu podaje raport, nie sam fakt istnienia testu |
| 15. Wpływ | [plans.impact](../api/plans.py), [Trial](../web/src/Trial.tsx), [RESEARCH.md](RESEARCH.md) | Rzeczywiste minuty, koszt i wysiłek są oddzielne od symulacji. Brak bazy i obserwacji nie staje się zerem. Normalizacja okresów nie dowodzi przyczynowości |
| 16. Demonstracja | [single-parent.json](../data/synthetic/single-parent.json), [two-dependents.json](../data/synthetic/two-dependents.json), [care-handoff.json](../data/synthetic/care-handoff.json), dowody w [evidence](evidence/) | Konflikt 45 minut, kontrpropozycja z konfliktem 15 minut, większy zapas, kilka miejsc i przekazanie. Osoby, praca, opieka, ceny i decyzje są syntetyczne |
| 17. Ryzyka wartości | [RESEARCH.md](RESEARCH.md), [OPERATIONS.md](OPERATIONS.md), komunikaty o brakach i odmowach | Aplikacja nie tworzy miejsca opieki ani zgody pracodawcy. Nie zawarto partnerstwa i nie potwierdzono modelu finansowania |
| 18. Zgłoszenie | [SUBMISSION.md](SUBMISSION.md), [materiały PDF/PPTX/MP4 i demo](MATERIALS.md), [AI_USAGE](../AI_USAGE.md), [THIRD_PARTY](../THIRD_PARTY.md), [PREEXISTING](../PREEXISTING.md) | Materiały do istniejącego etapu New Idea i publiczne demo zostały zlecone. Nie utworzono drugiego wpisu ani nie wysłano ostatecznego zgłoszenia. Nie ma potwierdzenia przyjęcia ani rozstrzygnięcia niejasności regulaminowych |

## Co dokładnie oblicza model

Jedna analiza obejmuje cały podany okres do 731 dni. Domyślne 28 dni jest ustawieniem formularza. Harmonogram umowy bez końca nie jest potwierdzany na nieograniczoną przyszłość. Konkretne daty w regule zastępują tygodniowe powtórzenie, a wyjątki usuwają wskazane dni. Czas letni i zimowy wymaga rozstrzygnięcia niejednoznacznych godzin.

Optymalizacja dotyczy jawnych godzin `start_min/start_max/step_minutes`, dopuszczonych zasobów, wskazanej kolejności miejsc i zdefiniowanych przekazań. Nie wyszukuje niewprowadzonych usług ani dowolnych tras i kolejności. Tytuł o minimalnej zmianie wymaga dowodu właściwych etapów. Limit zasobów, niepełna domena tras albo nieznane istotne dane nie stanowią dowodu rzeczywistej niemożliwości.

Koszt jest liczony w groszach w okresie analizy. Cena przejazdu i prawo do ulgi są osobnymi danymi; OTP nie wylicza uprawnień. Podróż, dojście od punktu, przekazanie i bufor zachowują swój zakres. Rozkład planowy nie jest gwarancją punktualności. Odwołanie opieki i dodatkowe opóźnienie są testami konkretnych zakłóceń, bez przypisania im wymyślonych prawdopodobieństw.

## Działania wymagające rzeczywistego wdrożenia i udziału ludzi

Końcowy niezależny audyt asystenta AI ma status `partial`. Potwierdzona i nadal otwarta wada dostępności: filtrowanie katalogu nie ogłasza liczby ani braku wyników w regionie `aria-live`/`status`. Widoczny komunikat pozostaje na stronie, ale czytnik ekranu może nie poinformować o zmianie bez przejścia do wyników. Nie deklarujemy zakończenia wszystkich napraw ani pełnego odbioru dostępności. Szczegółowe ustalenia i ich odrębna weryfikacja są opisane w [VALIDATION.md](VALIDATION.md).

- Wykonanie wywiadów oraz porównania użyteczności według protokołu, z rzeczywistymi uczestniczkami i osobami układającymi grafik.
- Uzgodnienie operatora danych, wsparcia, procedury incydentów, finansowania i zasad utrzymania katalogu.
- Sprawdzenie szyfrowania woluminów hosta, kopii poza hostem i odtworzenia w środowisku docelowym. Szyfrowanie rekordów nie dowodzi konfiguracji całej infrastruktury.
- Potwierdzenie platformy zgłoszenia, terminu, strefy czasu i kwalifikowalności prac. Literalne rozbieżności materiałów zachowano w pakiecie zgłoszeniowym.

Żaden z tych punktów nie jest zastępowany wygenerowanymi ankietami, fikcyjnymi opiniami lub danymi demonstracyjnymi. Dostarczone protokoły i narzędzia umożliwiają dalszą walidację; nie oznaczają jej wykonania.
