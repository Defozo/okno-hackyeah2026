# Publiczna brama Okna

Worker ESM udostępnia demo Okna oraz materiały konkursowe. Przekazuje żądania aplikacji do kontrolowanego endpointu demonstracyjnego, ogranicza nagłówki i sprawdza sekret bramy. Publiczne pliki pobiera z magazynu obiektów. `/materialy/` działa także przy niedostępnych obliczeniach.

Lokalne sprawdzenie wymaga Node.js 24, bez instalowania zależności:

```powershell
npm --prefix public-demo test
npm --prefix public-demo run build
npm --prefix public-demo run validate
```

Wynik budowy: `public-demo/dist/server/index.js`. Snapshot nie zawiera `.openai/`, stanu konta ani tokenów. Jego skrypt budowania kopiuje wyłącznie worker i nie tworzy przypisania do hostingu.

Własne wdrożenie wymaga zgodnego runtime Workers, bindingu `BUCKET`, sekretu `OKNO_DEMO_GATEWAY_KEY`, własnej domeny w stałej `ORIGIN` i kontrolowanego upstreamu. Pliki prezentacji, filmu oraz pakietu publikuje operator przez chronione ścieżki `/_ops/materials/`. Zasady uruchomienia obecnego stosu opisano w [PUBLIC_DEMO.md](../docs/PUBLIC_DEMO.md). Te dodatkowe usługi nie są wymagane do uruchomienia aplikacji na localhost.
