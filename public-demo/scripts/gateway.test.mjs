import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.js';
const origin = 'https://okno-impacther-2026.defozo.chatgpt.site';
const key = 'unit-test-key-only-not-a-deployment-secret';
const memory = new Map();
const bucket = {
  async put(name, value, options = {}) {memory.set(name, {value: typeof value === 'string' ? value : await new Response(value).text(), options});},
  async get(name) {
    const item = memory.get(name);
    if (!item) return null;
    return {json: async () => JSON.parse(item.value), body: item.value, size: new TextEncoder().encode(item.value).length, httpEtag: '"test"', customMetadata: item.options.customMetadata,
      writeHttpMetadata(headers) {for (const [k, v] of Object.entries(item.options.httpMetadata ?? {})) headers.set(k === 'contentType' ? 'content-type' : 'cache-control', v);}};
  },
};
const env = {BUCKET: bucket, OKNO_DEMO_GATEWAY_KEY: key};
const req = (path, init = {}) => new Request(origin + path, init);
const auth = {authorization: 'Bearer ' + key};

test('control plane denies unauthenticated writes', async () => {
  const result = await worker.fetch(req('/_ops/tunnel', {method: 'PUT', body: '{"url":"https://safe.ngrok-free.app"}'}), env);
  assert.equal(result.status, 404);
  assert.equal(memory.size, 0);
});
test('control plane rejects private URLs and embedded credentials', async () => {
  for (const url of ['http://127.0.0.1', 'https://localhost', 'https://safe.ngrok-free.app.evil.test', 'https://secret@safe.ngrok-free.app', 'https://safe.ngrok-free.app/a']) {
    const result = await worker.fetch(req('/_ops/tunnel', {method: 'PUT', headers: auth, body: JSON.stringify({url})}), env);
    assert.equal(result.status, 400, url);
  }
});
test('missing connection is explicit unavailable, not a simulated app', async () => {
  assert.equal((await worker.fetch(req('/'), env)).status, 503);
});
test('material page remains available while the calculation host is disconnected', async () => {
  const result = await worker.fetch(req('/materialy/'), env);
  assert.equal(result.status, 200);
  assert.match(await result.text(), /New Idea/);
});
test('unknown origins are rejected', async () => {
  assert.equal((await worker.fetch(new Request('https://evil.example/'), env)).status, 421);
});
test('connection registration accepts only an authenticated expected tunnel', async () => {
  const result = await worker.fetch(req('/_ops/tunnel', {method: 'PUT', headers: auth, body: JSON.stringify({url: 'https://demo.ngrok-free.app'})}), env);
  assert.equal(result.status, 200);
  assert.equal(JSON.parse(memory.get('private/connection.json').value).url, 'https://demo.ngrok-free.app');
});
test('proxy preserves the browser origin and CSRF, strips unrelated cookies and authorization', async () => {
  const original = globalThis.fetch;
  let seen;
  globalThis.fetch = async (url, init) => {seen = {url: String(url), ...init}; return Response.json({ok: true}, {headers: {'set-cookie': 'okno_session=test; HttpOnly; Secure; SameSite=Strict'}});};
  try {
    const result = await worker.fetch(req('/api/plans', {method: 'POST', headers: {'origin': 'https://attacker.example', 'x-csrf-token': 'csrf', 'authorization': 'Bearer unrelated', 'cookie': 'private_platform_cookie=value; okno_session=test; other=value'}, body: '{}'}), env);
    assert.equal(result.status, 200);
    assert.equal(seen.headers.get('origin'), 'https://attacker.example');
    assert.equal(seen.headers.get('x-csrf-token'), 'csrf');
    assert.equal(seen.headers.get('cookie'), 'okno_session=test');
    assert.equal(seen.headers.get('authorization'), null);
    assert.equal(seen.headers.get('x-okno-gateway'), key);
    assert.equal(result.headers.get('cache-control'), 'no-store');
    assert.match(result.headers.get('set-cookie'), /Secure/);
  } finally {globalThis.fetch = original;}
});
test('public files require authenticated upload and an allowlisted name', async () => {
  const invalid = await worker.fetch(req('/_ops/materials/private.json', {method: 'PUT', headers: auth, body: '{}'}), env);
  assert.equal(invalid.status, 404);
  const data = '%PDF-fixture';
  const upload = await worker.fetch(req('/_ops/materials/prezentacja.pdf', {method: 'PUT', headers: {...auth, 'content-length': String(data.length), 'x-content-sha256': 'a'.repeat(64)}, body: data}), env);
  assert.equal(upload.status, 200);
  const download = await worker.fetch(req('/materialy/prezentacja.pdf'), env);
  assert.equal(download.status, 200);
  assert.equal(await download.text(), data);
  assert.equal(download.headers.get('content-type'), 'application/pdf');
});
