# Publiczna ekstrakcja: zakres i wykonany pomiar

DEFOZO SOFTWARE HOUSE, Michał Kiełtyka. Stan 2026-10-03. Etykiety przygotowano z pomocą asystenta AI przed uruchomieniem ekstrakcji. Nie przeprowadzono niezależnego audytu człowieka.

[Bieżący korpus](../data/extraction/public-pl.json) zawiera 67 rzeczywistych polskich fragmentów z 36 publicznych URL. Każdy ma dokładny tekst, URL, datę pobrania, hash zachowanego tekstu źródłowego i oczekiwane wartości. Nowe fragmenty są niezmienionymi podciągami tekstu oczyszczonego z HTML. To wybór celowy, bez twierdzenia reprezentatywności.

| Zakres etykiet | Liczba |
| --- | ---: |
| Dodatnie godziny | 6 |
| Dodatnia cena, okres i składnik kosztu | 9 |
| Oba pola puste | 52 |
| Negacja rzeczywistego zakresu godzin | 1 |
| Wyłączona cena dodatkowego pakietu | 1 |

Źródła nowych przykładów obejmują żłobki, szkoły prowadzące kursy, uczelnie i urząd. Występują koszty za godzinę, dzień, miesiąc oraz jednorazowe. Zbiór zawiera również cenę przybliżoną i kilka przedziałów godzin, których prosta struktura pojedynczego zakresu nie może bezpiecznie reprezentować. W repozytorium pozostają dodatkowe 35 przypadków syntetycznych; nie zwiększają liczby publicznych przykładów.

[Końcowy pomiar](../data/extraction/groq-benchmark.json) dla `openai/gpt-oss-120b` zakończył się wynikiem **64/67**. Mierzy cały pipeline Groq i walidatora, w tym kwotę, okres oraz składnik kosztu. Wszystkie zwrócone wyniki odpowiadały etykietom. Trzy przypadki zakończyły się odmową walidacji `ImportRejected`, liczoną jako porażka:

- `public-051`: model wskazał niezgodny składnik przy czesnym miesięcznym.
- `public-055`: model wskazał niezgodny składnik przy dodatkowej opiece poza godzinami.
- `public-064`: model próbował odczytać cenę wyłączonego pakietu pomimo negacji.

Te odrzucenia wymagają ręcznego sprawdzenia; nie przedstawiamy ich jako poprawnego pustego pola. Wynik nie jest dokładnością samego surowego modelu ani gwarancją jakości innych ofert. Godziny i kwoty nie oznaczają przyjęcia do placówki lub pełnego kosztu konkretnej rodziny.

Pierwotny [raport 50/50](../data/extraction/groq-benchmark-original50.json) jest historyczny. Pierwszy przebieg rozszerzonego zbioru dał [54/67](../data/extraction/groq-benchmark-expanded-before-fixes.json). Ujawnił między innymi utratę określenia „około” przez przycięty cytat. Poprawki wymagają pełnego kontekstu, związku pojedynczej kwoty z okresem, zachowania składnika kosztu i odrzucania zamknięcia oraz wielu przedziałów. Kolejne przebiegi zachowano w `data/extraction/history/`; błędy nie są usuwane z mianownika.

Testy regresji w `tests/test_importer.py` sprawdzają te przypadki, wszystkie etykiety regułowego importera, przeniesienie składnika kosztu do katalogu i ponowną walidację przy przeglądzie publikowanych faktów. Nie wybieraliśmy korzystnego przebiegu z wielu równoważnych prób: historyczne pomiary odpowiadają kolejnym zmianom walidatora, instrukcji i zakresu pomiaru.

Odtworzenie końcowego pomiaru z katalogu projektu i zainstalowanym `psst`:

```powershell
psst GROQ_API_KEY -- docker run --rm --memory=2g --entrypoint python -e GROQ_API_KEY --mount "type=bind,source=$((Get-Location).Path),target=/app" okno-app:local -m data.extraction.benchmark_groq
```

Komenda przekazuje do modelu wyłącznie teksty wersjonowanego korpusu oznaczone jako publiczne. Poprzedni raport automatycznie trafia do katalogu historii. Zewnętrzny model może zwrócić inny wynik mimo temperatury zero. Pełne pobrane strony pozostają roboczym materiałem poza pakietem, w `.runtime/corpus-expansion-pages.json`. `extend_public.py` zachowuje daty tych pobrań; ponowne zbudowanie etykiet z cache nie oznacza nowego pobrania stron.
