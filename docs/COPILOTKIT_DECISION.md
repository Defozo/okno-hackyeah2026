# Ocena CopilotKit dla Okna

Decyzja z 3 października 2026: **bez integracji w obecnej wersji**. Okno prowadzi użytkowniczkę od godzin pracy, opieki i dojazdów do obliczonego wariantu, karty do rozmowy i próby. Dodatkowy czat nie ma obecnie wykazanego zastosowania, które skracałoby tę ścieżkę.

Sprawdzono [stronę CopilotKit](https://www.copilotkit.ai/), [dokumentację](https://docs.copilotkit.ai/), [quickstart](https://docs.copilotkit.ai/quickstart) i [Frontend Tools](https://docs.copilotkit.ai/frontend-tools). SDK obsługuje aplikacje React/Vite, interfejs rozmowy i wywoływanie funkcji klienta przez agenta. Techniczne dopasowanie do frontendu Okna jest możliwe. Quickstart dodaje runtime oraz agenta połączonego z modelem.

Oceniono trzy zastosowania. Wypełnianie grafiku przez rozmowę wymagałoby przekazania agentowi kontekstu osobistego planu i osobnej kontroli błędów interpretacji. Objaśnianie konfliktu powielałoby wynik i źródła już dostępne przy wariancie. Przygotowanie propozycji dla pracodawcy jest obsługiwane przez kartę z zatwierdzanym zakresem pól. W każdym przypadku solver, walidator i zapisane ustalenia nadal musiałyby rozstrzygać o wykonalności i gotowości do próby. To ocena projektowa na podstawie bieżącej ścieżki, nie wynik badania porównawczego z użytkowniczkami.

Nie dodano paczek, runtime, sekretów ani wywołań modelu. Funkcje, obliczenia i model prywatności pozostały bez zmian. Ponowna ocena ma sens, jeżeli obserwacje z używania formularza wykażą konkretną barierę, którą obsługa głosowa lub rozmowa usuwa. Wtedy należy porównać czas ukończenia i liczbę błędów, z zachowaniem kontroli użytkowniczki nad zmianami danych i eksportem.
