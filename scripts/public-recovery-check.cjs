/* Controlled restart of this project's public tunnel; no secrets in report. */
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto'), cp=require('node:child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../.venv/Lib/site-packages/playwright/driver/package');
const root=path.resolve(__dirname,'..'), origin='https://okno-impacther-2026.defozo.chatgpt.site';
const report={started_at:new Date().toISOString(),base_url:origin,tunnel_container:'okno-demo-tunnel-1',verified:false,mocks_used:false,tls_certificate_validation:true,fresh_session_test:true};
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const started=()=>cp.execFileSync('docker',['inspect','okno-demo-tunnel-1','--format','{{.State.StartedAt}}'],{encoding:'utf8'}).trim();
async function tunnelFingerprint(){const r=await fetch('http://127.0.0.1:18432/api/tunnels',{signal:AbortSignal.timeout(5000)}); const data=await r.json(); return hash(data.tunnels.find(t=>t.public_url.startsWith('https://')).public_url);}
(async()=>{
 let browser;
 try{
 report.container_started_before=started(); report.tunnel_fingerprint_before=await tunnelFingerprint();
 report.restart_requested_at=new Date().toISOString();
 cp.execFileSync('docker',['restart','okno-demo-tunnel-1'],{timeout:45000,stdio:'pipe'});
 report.container_started_after=started();
 if(report.container_started_before===report.container_started_after)throw Error('Container did not restart');
 const deadline=Date.now()+150000; let ready=false;
 report.health_checks=[];
 while(Date.now()<deadline){
  try{const r=await fetch(origin+'/health/ready',{headers:{'User-Agent':'Okno-demo-recovery-check/1.0'},signal:AbortSignal.timeout(10000)});report.health_checks.push({at:new Date().toISOString(),status:r.status});if(r.ok&&(await r.json()).status==='ready'){ready=true;break;}}
  catch(e){report.health_checks.push({at:new Date().toISOString(),error_kind:e.name});}
  await new Promise(resolve=>setTimeout(resolve,5000));
 }
 if(!ready)throw Error('Public readiness did not recover before deadline');
 report.recovered_at=new Date().toISOString();
 report.tunnel_fingerprint_after=await tunnelFingerprint();
 report.tunnel_address_changed=report.tunnel_fingerprint_before!==report.tunnel_fingerprint_after;
 const log=cp.execFileSync('docker',['logs','--since',report.restart_requested_at,'okno-demo-connector-1'],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
 report.connector_events=log.split('\n').flatMap(line=>{try{const e=JSON.parse(line);return e.event==='connection_registered'?[{event:e.event,at:e.at}]:[];}catch{return []}});
 report.connector_registration_observed=report.connector_events.length>0;
 browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'pl-PL',ignoreHTTPSErrors:false});
 report.initial_cookie_count=(await context.cookies()).length;if(report.initial_cookie_count!==0)throw Error('Expected empty context');
 const page=await context.newPage();report.page_errors=[];page.on('pageerror',e=>report.page_errors.push(e.message));
 await page.goto(origin,{waitUntil:'domcontentloaded',timeout:60000});
 await page.getByRole('combobox',{name:'Wybierz przykład'}).selectOption('single-parent',{timeout:30000});
 const replace=page.getByRole('button',{name:'Otwórz przykład',exact:true});if(await replace.isVisible())await replace.click();
 const solved=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/solve'&&r.request().method()==='POST',{timeout:60000});
 await page.getByRole('button',{name:'Sprawdź mój plan',exact:true}).click();
 const response=await solved;report.solve_http_status=response.status();if(!response.ok())throw Error('Public solve failed');
 const result=await response.json();report.solver_status=result.status;
 await page.locator('.alternative').first().waitFor({timeout:30000});
 report.alternatives=await page.locator('.alternative').count();report.conflict_contains_45=(await page.locator('.conflict-card').innerText()).includes('45');
 if(report.alternatives<2||!report.conflict_contains_45)throw Error('Public result differs from expected demo');
 await page.screenshot({path:path.join(root,'docs/evidence/public/recovery-results.png'),fullPage:true});
 const materials=await context.request.get(origin+'/materialy/',{timeout:30000});report.materials_http_status=materials.status();if(materials.status()!==200)throw Error('Materials unavailable');
 if(report.page_errors.length)throw Error('Unexpected browser errors');
 report.verified=true;report.completed_at=new Date().toISOString();
 await context.close();
 }catch(e){report.failure=e.message;throw e;}
 finally{fs.writeFileSync(path.join(root,'docs/evidence/public-recovery.json'),JSON.stringify(report,null,2)+'\n');if(browser)await browser.close();}
 console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1;});

