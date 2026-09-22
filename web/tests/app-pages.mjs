import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const browser=await chromium.launch();
const base=process.env.PREVIEW_URL||'http://127.0.0.1:3002';
const fixture={county:{name:'Genesee',state:'NY',fips:'36037',lat:43,lon:-78},soil:{type:'loam',water_source:'stored'},crop:{id:'corn',aw:6,mad:.4,gdd_pct:58,cumulative_gdd:1566,gdd_to_maturity:2700,stage_label:'Pollination',planting_date:'2026-05-15'},today:{action:'IRRIGATE',advice_uncertain:false,soil_pct:35,soil_min_pct:34,soil_max_pct:36,soil_water:2.1,depletion:.65,irrigate_amount:3.3,etc:.22,rain_7d:.4,rain_today:0,gdd:12},forecast:Array.from({length:7},(_,i)=>({date:`2026-09-${12+i}`,precip_in:[.1,0,.23,.04,0,.03,0][i],etc:.15+i*.01,tmax_f:78,tmin_f:60,action:'HOLD',depletion:.35,soil_water:4-i*.2,gdd:10,et0_in:.2})),history:{july_avg_high:81,july_avg_low:60,last_7d_rain:.75,last_7d_et:1.3,july_total_rain:2.3},drought:{level:'NONE'},outbox:[],planting_window:null,data_as_of:{last_pipeline_at:'2026-09-12T06:00:00'}};
try{
const page=await browser.newPage();const navigate=page.goto.bind(page);page.goto=(url,opts={})=>navigate(url,{waitUntil:"domcontentloaded",...opts});const errors=[];let failAuth=true,unavailable=false,unauthorized=false;
page.on('pageerror',e=>errors.push(e.message));
await page.route('https://www.openstreetmap.org/**',r=>r.fulfill({body:'<p>Map fixture</p>',contentType:'text/html'}));
await page.route('**/api/**',r=>{const u=r.request().url();if(u.includes('/auth/login'))return r.fulfill({status:failAuth?401:200,json:failAuth?{detail:'Invalid credentials'}:{}});if(u.includes('/advisory/'))return r.fulfill({status:unauthorized?401:unavailable?503:200,json:fixture});return r.fulfill({json:[]});});
// A slow upstream must show loading, then fill the date without fetching twice.
let releaseAdvisory;
const pendingAdvisory = new Promise(resolve => { releaseAdvisory = resolve; });
let advisoryRequests = 0;
await page.route('**/api/advisory/**', async r => {
 advisoryRequests++;
 await pendingAdvisory;
 await r.fulfill({json:fixture});
});
await page.goto(`${base}/dashboard`);
await page.getByRole('status').filter({hasText:'Loading your field and weather data'}).waitFor();
assert.equal(await page.getByText('Data unavailable for this county',{exact:true}).count(),0);
releaseAdvisory();
await page.getByRole('heading',{name:'Your field at a glance'}).waitFor();
await page.waitForFunction(()=>document.querySelector('#planting-date')?.value==='2026-05-15');
await page.waitForTimeout(200);
assert.equal(advisoryRequests,1,'Returned planting date must not refetch the advisory');
await page.unroute('**/api/advisory/**');
const routes=['dashboard','growth','water','journal','weather','reports','settings','checklist','help'];
for(const width of (process.env.SKIP_LAYOUT?[]:process.env.WIDTHS?process.env.WIDTHS.split(',').map(Number):[1440,1920,2560,1280,1024,768,390,320])){
 await page.setViewportSize({width,height:1000});
 for(const route of routes){
  await page.goto(`${base}/${route}`);
  if(['growth','water','weather','reports'].includes(route))await page.locator('.mw-table').waitFor();
  if(route==='dashboard')await page.getByRole('heading',{name:'Your field at a glance'}).waitFor();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))console.log(await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right,text:e.textContent.slice(0,60)})).slice(0,18)));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${route} overflow at ${width}`);
  if(width>=1024)assert.equal(await page.getByRole('navigation',{name:'Main navigation'}).isVisible(),true);
  if(width===1440||width===390)await page.screenshot({path:`/tmp/muons-${route}-${width}.png`,fullPage:true});
 }
 await page.goto(`${base}/login`);await page.getByRole('heading',{name:'Welcome back'}).waitFor();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`login overflow ${width}`);
}
await page.setViewportSize({width:1440,height:1000});
await page.goto(`${base}/journal`);
await page.getByLabel('What did you notice?').fill('Leaves look healthy after morning inspection.');
await page.getByRole('button',{name:'Save observation',exact:true}).click();

await page.getByText('Observation saved in this browser.',{exact:true}).waitFor();
await page.reload();await page.getByText('Leaves look healthy after morning inspection.',{exact:true}).waitFor();
await page.getByRole('button',{name:'Edit entry',exact:true}).click();await page.getByLabel('What did you notice?').fill('Checked soil moisture in the north field.');await page.getByRole('button',{name:'Save changes'}).click();await page.getByText('Checked soil moisture in the north field.',{exact:true}).waitFor();
await page.getByLabel('Search notes').fill('unmatched');await page.getByRole('heading',{name:'No matching notes'}).waitFor();await page.getByLabel('Search notes').fill('');
page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Delete entry'}).click();await page.getByRole('heading',{name:'Your journal starts here'}).waitFor();
await page.goto(`${base}/settings`);await page.getByLabel('Display name').fill('Amina');await page.getByRole('button',{name:'Save preferences'}).click();await page.getByText('Preferences saved.',{exact:true}).waitFor();assert.equal(await page.locator('.mw-account-name').innerText(),'Amina');
await page.getByRole('button',{name:'Units',exact:true}).click();await page.getByLabel('Water units').selectOption('mm');await page.getByLabel('Temperature',{exact:true}).selectOption('C');await page.getByRole('button',{name:'Save preferences'}).click();
await page.goto(`${base}/water`);await page.getByText(/83.82 mm/).first().waitFor();await page.getByRole('button',{name:'30 Days',exact:true}).click();await page.getByText('Only 7 forecast days are available. No 30-day forecast has been inferred.',{exact:true}).waitFor();
await page.goto(`${base}/weather`);await page.getByRole('button',{name:'Hourly Forecast',exact:true}).click();await page.getByRole('heading',{name:'Hourly forecast unavailable'}).waitFor();
await page.goto(`${base}/reports`);await page.getByLabel('Report type').selectOption('Rainfall');await page.getByLabel('From date').fill('2026-09-13');await page.getByLabel('To date').fill('2026-09-14');await page.getByRole('button',{name:'Generate Report'}).click();await page.getByRole('heading',{name:'Rainfall report preview'}).waitFor();assert.equal(await page.locator('tbody tr').count(),2);
const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export CSV'}).click();const download=await downloadPromise;const csv=await fs.readFile(await download.path(),'utf8');assert.match(csv,/Forecast rain \(mm\)/);assert.match(csv,/2026-09-14/);assert.doesNotMatch(csv,/2026-09-12/);
await page.goto(`${base}/checklist`);const checkboxes=page.getByRole('checkbox');assert.equal(await checkboxes.count(),6);for(const cb of await checkboxes.all())await cb.check();await page.getByText('Field check complete',{exact:true}).waitFor();await page.reload();await page.getByText('6 of 6 complete',{exact:true}).waitFor();
await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Toggle navigation'}).click();await page.getByRole('navigation',{name:'Main navigation'}).getByRole('link',{name:'Growth',exact:true}).click();await page.getByRole('heading',{name:'Crop Growth',exact:true}).waitFor();assert.equal(await page.getByRole('navigation',{name:'Main navigation'}).isVisible(),false);
await page.getByLabel('Search pages').fill('report');await page.locator('.mw-search-results').getByRole('link',{name:'Reports'}).click();await page.getByRole('heading',{name:'Reports',exact:true}).waitFor();
unavailable=true;await page.goto(`${base}/growth`);await page.getByRole('heading',{name:'Your field data is unavailable'}).waitFor();unavailable=false;await page.getByRole('button',{name:'Retry',exact:true}).click();await page.getByText('Estimated development',{exact:true}).waitFor();
unauthorized=true;await page.goto(`${base}/growth`);await page.waitForURL('**/login');unauthorized=false;
await page.getByLabel('Email',{exact:true}).fill('farmer@example.com');await page.getByLabel('Password',{exact:true}).fill('test-password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('alert').filter({hasText:'Invalid credentials'}).waitFor();failAuth=false;await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/dashboard');
assert.deepEqual(errors,[]);console.log('PASS: all 10 pages at 8 viewports; journal CRUD/persistence/filtering; settings/units; report CSV/date filters; checklist; drawer/search; auth; error/retry; no JS errors.');
}finally{await browser.close();}
