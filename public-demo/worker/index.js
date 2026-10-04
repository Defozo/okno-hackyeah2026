const ORIGIN = 'https://okno-impacther-2026.defozo.chatgpt.site';
const FILES = {
  'prezentacja.pdf': 'application/pdf',
  'prezentacja.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'demo.mp4': 'video/mp4',
  'okno-song-20261004-17dbd75070bd.mp4': 'video/mp4',
  'napisy.vtt': 'text/vtt; charset=utf-8',
  'pakiet.zip': 'application/zip',
};
const SAFE_HEADERS = ['accept', 'accept-language', 'content-type', 'origin', 'x-csrf-token', 'idempotency-key', 'if-none-match', 'range', 'if-range'];
const SECURITY = {
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'no-referrer',
  'x-robots-tag': 'noindex, nofollow',
  'strict-transport-security': 'max-age=31536000',
};

function json(value, status = 200) {
  return Response.json(value, {status, headers: {...SECURITY, 'cache-control': 'no-store'}});
}

async function authorized(request, env) {
  if (!env.OKNO_DEMO_GATEWAY_KEY || !request.headers.get('authorization')?.startsWith('Bearer ')) return false;
  const input = request.headers.get('authorization').slice(7);
  if (input.length > 200) return false;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([input, env.OKNO_DEMO_GATEWAY_KEY].map(value => crypto.subtle.digest('SHA-256', enc.encode(value))));
  const aa = new Uint8Array(a), bb = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < aa.length; i++) diff |= aa[i] ^ bb[i];
  return diff === 0;
}

function validUpstream(raw) {
  try {
    const url = new URL(raw);
    return url.protocol === 'https:' && !url.port && !url.username && !url.password && !url.search && !url.hash && url.pathname === '/' && /^[a-z0-9-]+\.ngrok-free\.(app|dev)$/.test(url.hostname);
  } catch { return false; }
}

async function operations(request, env, path) {
  if (!await authorized(request, env)) return json({error: 'Not found'}, 404);
  if (path === '/_ops/tunnel' && request.method === 'PUT') {
    if (Number(request.headers.get('content-length')) > 2048) return json({error: 'Too large'}, 413);
    const raw = await request.text();
    if (raw.length > 2048) return json({error: 'Too large'}, 413);
    let data;
    try { data = JSON.parse(raw); } catch { return json({error: 'Invalid JSON'}, 400); }
    if (!validUpstream(data.url)) return json({error: 'Invalid endpoint'}, 400);
    await env.BUCKET.put('private/connection.json', JSON.stringify({url: new URL(data.url).origin, updated_at: new Date().toISOString()}), {httpMetadata: {contentType: 'application/json'}});
    return json({registered: true});
  }
  if (path === '/_ops/status' && request.method === 'GET') {
    const object = await env.BUCKET.get('private/connection.json');
    const connection = object ? await object.json() : null;
    return json({connected: !!connection, updated_at: connection?.updated_at ?? null});
  }
  const name = path.replace(/^\/_ops\/materials\//, '');
  if (path.startsWith('/_ops/materials/') && FILES[name] && request.method === 'PUT') {
    const size = Number(request.headers.get('content-length'));
    if (!Number.isSafeInteger(size) || size < 1 || size > 100_000_000) return json({error: 'Invalid size'}, 413);
    const sha = request.headers.get('x-content-sha256') ?? '';
    if (!/^[a-f0-9]{64}$/.test(sha)) return json({error: 'Missing digest'}, 400);
    await env.BUCKET.put('public/' + name, request.body, {
      httpMetadata: {contentType: FILES[name], cacheControl: 'public, max-age=300'},
      customMetadata: {sha256: sha, uploaded_at: new Date().toISOString()},
    });
    return json({uploaded: name, sha256: sha, bytes: size});
  }
  return json({error: 'Not found'}, 404);
}

async function material(request, env, name) {
  if (!FILES[name] || !['GET', 'HEAD'].includes(request.method)) return json({error: 'Not found'}, 404);
  const object = await env.BUCKET.get('public/' + name, {range: request.headers});
  if (!object) return json({error: 'Plik nie jest jeszcze dostępny.'}, 404);
  const headers = new Headers(SECURITY);
  object.writeHttpMetadata(headers);
  headers.set('etag', object.httpEtag);
  headers.set('accept-ranges', 'bytes');
  headers.set('x-content-sha256', object.customMetadata?.sha256 ?? '');
  headers.set('content-disposition', `${name.endsWith('.pdf') || name.endsWith('.mp4') ? 'inline' : 'attachment'}; filename="${name}"`);
  let status = 200;
  if (request.headers.has('range') && object.range) {
    const offset = object.range.offset ?? Math.max(0, object.size - object.range.suffix);
    const length = object.range.length ?? object.size - offset;
    headers.set('content-range', `bytes ${offset}-${offset + length - 1}/${object.size}`);
    headers.set('content-length', String(length));
    status = 206;
  } else headers.set('content-length', String(object.size));
  return new Response(request.method === 'HEAD' ? null : object.body, {status, headers});
}

const materialPage = `<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Okno: materiały dla jury</title><style>
body{margin:0;background:#fbf7f2;color:#352c35;font:18px/1.55 system-ui,sans-serif}main{max-width:900px;margin:auto;padding:32px 22px}h1{font-size:clamp(32px,5vw,48px);line-height:1.15}h2{font-size:26px;margin-top:36px}a{color:#643d56;text-underline-offset:4px}a:focus-visible{outline:3px solid #b65334;outline-offset:5px}li{margin:12px 0}.demo{display:inline-block;background:#643d56;color:white;padding:12px 22px;border-radius:8px;text-decoration:none}video{width:100%;background:#4c2b41;border-radius:10px}small{font-size:15px}ol{padding-left:24px}</style></head><body><main>
<p>DEFOZO SOFTWARE HOUSE<br>Michał Kiełtyka · New Idea</p><h1>Okno: materiały dla jury</h1><p><strong>Praca kończy się o 17:00. Odbiór z dojazdem i buforem wypada o 17:45.</strong> Okno wskazuje konflikt, porównuje dopuszczalne zmiany i przygotowuje konkretne godziny do rozmowy z pracodawcą.</p>
<p><a class="demo" href="/">Otwórz interaktywne demo</a></p><p><small>Przykład demonstracyjny. Korzystaj wyłącznie z danych testowych.</small></p>
<h2>Zobacz produkt w działaniu</h2><ul><li><a href="/materialy/prezentacja.pdf">Prezentacja PDF, 10 slajdów</a></li><li><a href="/materialy/prezentacja.pptx">Prezentacja PPTX z notatkami</a></li><li><a href="/materialy/demo.mp4">Film demonstracyjny MP4 z lektorem</a></li><li><a href="/materialy/okno-song-20261004-17dbd75070bd.mp4">Wariant muzyczny</a> <small>MP4, 2:30. Muzyka i wokal: Eleven Music. Autorski tekst z pomocą AI.</small></li><li><a href="/materialy/napisy.vtt">Polskie napisy VTT</a></li><li><a href="/materialy/pakiet.zip">Pakiet materiałów ZIP</a></li></ul>
<video controls preload="metadata" aria-label="Film demonstracyjny Okna"><source src="/materialy/demo.mp4" type="video/mp4"><track src="/materialy/napisy.vtt" kind="captions" srclang="pl" label="Polskie napisy"></video>
<h2>Sprawdź, które godziny rozwiązują konflikt</h2><ol><li>Otwórz przykład „45 minut do zmiany” i wybierz „Sprawdź mój plan”.</li><li>Porównaj dwa warianty: 08:15–16:15 usuwa konflikt, a 08:00–16:00 daje dodatkowe 15 minut zapasu. Oba zachowują 40 godzin pracy tygodniowo w tej symulacji i wymagają zgody pracodawcy.</li><li>Przejdź do uzgodnień. Sprawdź kartę pracodawcy z proponowanymi godzinami, bez danych rodziny, i pobierz PDF.</li><li>Zapisz plan, jeśli chcesz sprawdzić dalszą ścieżkę. Wpisz demonstracyjną akceptację, rozpocznij próbę i pobierz grafik do kalendarza. Formularz wyniku czeka na obserwacje z próby.</li></ol>
<h2>Ty wybierasz, co zapiszesz i udostępnisz</h2><p>Demo otworzysz bez konta. Zapis planu jest dobrowolny, a dostęp do niego przypisany do tej przeglądarki. Pobranie karty nie wysyła jej i nie oznacza zgody drugiej strony ani rezerwacji opieki.</p><p><small>Obliczenia wymagają dostępnego serwera demonstracyjnego i połączenia z internetem. Prezentację oraz film możesz otworzyć także podczas przerwy w działaniu aplikacji.</small></p></main></body></html>`;

function unavailable() {
  return new Response('<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Okno: chwilowa przerwa</title><main style="max-width:650px;margin:10vh auto;padding:24px;font:20px/1.5 system-ui"><h1>Demo chwilowo nie odpowiada</h1><p>Spróbuj ponownie za chwilę. Obliczenia wymagają połączenia z serwerem demonstracyjnym.</p><p><a href="/materialy/">Otwórz prezentację i film</a></p></main></html>', {status: 503, headers: {...SECURITY, 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'retry-after': '15'}});
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.origin !== ORIGIN) return json({error: 'Unknown origin'}, 421);
    try {
      if (url.pathname.startsWith('/_ops/')) return await operations(request, env, url.pathname);
      if (url.pathname === '/materialy/' || url.pathname === '/materialy') {
        if (!['GET', 'HEAD'].includes(request.method)) return json({error: 'Method not allowed'}, 405);
        return new Response(request.method === 'HEAD' ? null : materialPage, {headers: {...SECURITY, 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=60', 'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; media-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"}});
      }
      if (url.pathname.startsWith('/materialy/')) return await material(request, env, url.pathname.slice('/materialy/'.length));
      if (!['GET', 'HEAD', 'POST', 'DELETE', 'OPTIONS'].includes(request.method)) return json({error: 'Method not allowed'}, 405);
      if (Number(request.headers.get('content-length')) > 2_000_000) return json({error: 'Request too large'}, 413);
      const configObject = await env.BUCKET.get('private/connection.json');
      if (!configObject) return unavailable();
      const config = await configObject.json();
      if (!validUpstream(config.url)) return unavailable();
      const headers = new Headers();
      for (const name of SAFE_HEADERS) if (request.headers.has(name)) headers.set(name, request.headers.get(name));
      const session = request.headers.get('cookie')?.split(';').map(s => s.trim()).find(s => s.startsWith('okno_session='));
      if (session) headers.set('cookie', session);
      headers.set('user-agent', 'Okno-Competition-Gateway/1');
      headers.set('ngrok-skip-browser-warning', '1');
      headers.set('x-okno-gateway', env.OKNO_DEMO_GATEWAY_KEY);
      const upstream = new URL(url.pathname + url.search, config.url);
      const response = await fetch(upstream, {method: request.method, headers, body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body, redirect: 'manual', signal: AbortSignal.timeout(45000)});
      if (response.headers.has('ngrok-error-code')) return unavailable();
      const outputHeaders = new Headers(response.headers);
      for (const [name, value] of Object.entries(SECURITY)) outputHeaders.set(name, value);
      outputHeaders.delete('server');
      outputHeaders.delete('x-powered-by');
      const location = outputHeaders.get('location');
      if (location) {
        const target = new URL(location, upstream);
        if (target.origin !== upstream.origin) return unavailable();
        outputHeaders.set('location', ORIGIN + target.pathname + target.search);
      }
      if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/health/')) outputHeaders.set('cache-control', 'no-store');
      return new Response(response.body, {status: response.status, headers: outputHeaders});
    } catch {
      return url.pathname.startsWith('/_ops/') ? json({error: 'Operation unavailable'}, 503) : unavailable();
    }
  },
};
