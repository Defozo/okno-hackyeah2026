# Utrzymanie Okna

## Usługi i sekrety

Podstawowy stos Compose obejmuje API ze zbudowanym interfejsem, PostgreSQL, migracje i usługę maintenance. Opcjonalne profile dodają OTP, lokalne HTTPS i importer. [README](../README.md) zawiera polecenia instalacji; [.env.example](../.env.example) dokumentuje publiczne ustawienia i nazwy sekretów.

`init-secrets.ps1` tworzy brakujące hasła bazy, sekret sesji i klucz szyfrowania w psst. `start.ps1` przekazuje je tylko do procesu Compose. Migrator i aplikacja używają osobnych ról bazy. Nie publikuj rozwiniętej konfiguracji Compose, sekretów, baz ani kopii danych. Zachowaj klucz szyfrowania w bezpiecznym magazynie: jest niezbędny do odczytu planów i odtworzenia kopii.

Port aplikacji jest domyślnie związany z localhost. Dla własnego publicznego wdrożenia skonfiguruj HTTPS, właściwy `APP_ORIGIN` i Secure cookie. Przed przetwarzaniem rzeczywistych danych określ administratora danych, informację dla użytkowniczek, dostęp administracyjny i kontakt wsparcia. Szyfrowanie rekordów uzupełnij szyfrowaniem woluminów hosta oraz kopią poza hostem.

## Sprawdzenie działania

```powershell
Invoke-RestMethod http://localhost:18430/health/ready
```

Po instalacji lub aktualizacji otwórz nową sesję przeglądarki, przelicz przykład, obejrzyj kartę PDF, zapisz testowy plan, dodaj odpowiedź i sprawdź kalendarz. Na końcu usuń testowy zapis. Gotowość API nie zastępuje sprawdzenia połączenia przez docelowy adres HTTPS.

## Retencja, kopie i odtworzenie

`PLAN_RETENTION_DAYS` domyślnie wynosi 30 dni bez aktywności, a `BACKUP_RETENTION_DAYS` 7 dni. Usługa maintenance raz na dobę usuwa wygasłe dane i tworzy zaszyfrowaną kopię. Operator może też uruchomić `python -m api.maintenance purge`, `backup --path KATALOG` albo `restore --path PLIK` w środowisku z rolą aplikacji, właściwym `DATABASE_URL` i `OKNO_ENCRYPTION_KEY`.

Kopia zawiera plany oraz rejestr usunięć. Odtworzenie respektuje znaczniki usunięcia, a przywrócone warunki wymagają nowej analizy. Przechowuj rejestr usunięć i klucz w sposób umożliwiający odtworzenie po utracie hosta. Regularnie wykonuj próbę odtworzenia w oddzielnym środowisku.

Kopia JSON użytkowniczki służy przeniesieniu planu do nowej sesji i nie zastępuje kopii operatora. Zaimportowany plan oraz dawne zgody wymagają ponownej oceny.

## Publiczny katalog

Rekord przechodzi stany `draft`, `reviewed`, `published`, `stale` i `withdrawn`. Przegląd i publikacja to osobne operacje poza publicznym API. Sprawdzaj źródło, datę ważności i cytat potwierdzający każde pole. Zmiana źródła wymaga ponownego przeglądu; wygaśnięcie nie może być automatycznie zastąpione nową datą.

Godziny sekretariatu nie oznaczają godzin opieki, a liczba miejsc nie potwierdza przyjęcia konkretnej osoby. Cena ma kwotę w groszach, okres oraz składnik, np. pobyt, wyżywienie, wpisowe albo kurs. Puste pole jest wartością nieznaną. Dane syntetyczne są oznaczone oddzielnie od publicznych rekordów.

```powershell
python -m api.importer --help
python -m api.importer import-csv publiczne-rekordy.csv --out data/catalog/review-inbox
python -m api.importer validate-json data/catalog/review-inbox/identyfikator.json
python -m api.importer transition data/catalog/review-inbox/identyfikator.json reviewed --reviewer operator
python -m api.importer transition data/catalog/review-inbox/identyfikator.json published --reviewer operator
```

Po sprawdzeniu przenieś pojedynczy rekord do `data/catalog/`. Skrzynka `review-inbox` nie jest widoczna w API. Wymagane kolumny CSV: `id,title,kind,source_url,fetched_at,terms`. Opcjonalne: `hours_start,hours_end,hours_excerpt,cost_grosze,cost_period,cost_excerpt,valid_from,valid_to`. Okres ceny to `hour`, `day`, `month` albo `once`. CSV nie pobiera automatycznie strony; redaktor sprawdza zgodność z aktualnym źródłem.

Importer ogranicza domeny, sprawdza adresy IP i przekierowania oraz usuwa aktywny HTML. Opcjonalne Groq i Firecrawl otrzymują wyłącznie publiczne materiały, z kluczami przekazanymi przez psst. Nie przesyłaj prywatnych grafików. Etykiety korpusu testowego przygotowano z pomocą AI; katalog nadal wymaga przeglądu operatora.

## Transport, zasoby i awarie

OTP wymaga zgodnych z analizowanymi datami feedów GTFS i grafu OSM. [Instrukcja](../infra/otp/README.md) opisuje pobranie, hashe, aktualizację i pamięć. Koszt utrzymania obejmuje host API i bazy, pamięć oraz budowę OTP, kopie i transfer, a przy opcjonalnym imporcie także usługi pobierania i ekstrakcji. Redakcja katalogu i wsparcie wymagają osobnego nakładu pracy. Podstawowa analiza nie wymaga płatnego API.

Przy awarii źródła użytkowniczka może pracować na własnych danych. Nie zastępuj brakującej trasy lub ceny wartością zerową. W przypadku podejrzenia wycieku ogranicz publiczny dostęp, zachowaj minimalne dane diagnostyczne i zmień odpowiednie sekrety. Nie zapisuj treści prywatnych planów ani kluczy w logach. [Działanie publicznego demo](PUBLIC_DEMO.md).
