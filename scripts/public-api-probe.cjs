const {request}=require('../.venv/Lib/site-packages/playwright/driver/package');
(async()=>{
 const origin='https://okno-impacther-2026.defozo.chatgpt.site';
 const api=await request.newContext({baseURL:origin,ignoreHTTPSErrors:false,userAgent:'Mozilla/5.0 OknoPublicVerification/1.0',timeout:60000});
 const session=await api.get('/api/session'); console.log('session',session.status());
 const token=(await session.json()).csrf_token;
 const examples=await api.get('/api/examples'); const data=await examples.json();
 console.log('examples',examples.status(),Object.keys(data),data.items.map(x=>({id:x.id,keys:Object.keys(x)})));
 const selected=data.items.find(x=>x.id==='single-parent');
 const started=Date.now();
 const result=await api.post('/api/solve',{headers:{Origin:origin,'X-CSRF-Token':token,'Idempotency-Key':require('node:crypto').randomUUID()},data:selected.scenario});
 const body=await result.text();
 console.log('solve',result.status(),((Date.now()-started)/1000).toFixed(2),result.headers()['content-type'],body.slice(0,600));
 await api.dispose();
})().catch(e=>{console.error(e.message);process.exitCode=1});
