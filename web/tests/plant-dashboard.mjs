import { chromium } from 'playwright';
import assert from 'node:assert/strict';
const browser = await chromium.launch({headless:true});
try {
const page = await browser.newPage();
let uncertain = false, growth = 58, action = 'IRRIGATE';
await page.route('**/api/**', route => route.fulfill({json: route.request().url().includes('advisory') ? {
county:{name:'Genesee',state:'NY',fips:'36037'},soil:{type:'loam',water_source:'stored'},
crop:{id:'corn',aw:6,mad:.4,gdd_pct:growth,stage_label:'Pollination'},
today:{action,advice_uncertain:uncertain,soil_pct:35,soil_min_pct:uncertain?10:34,soil_max_pct:uncertain?80:36,soil_water:2.1,depletion:.65,irrigate_amount:3.3,etc:.22,rain_7d:.4,rain_today:0,gdd:12},
forecast:Array.from({length:7},(_,i)=>({date:`2026-09-${12+i}`,precip_in:[.1,0,.23,.04,0,.03,0][i],etc:.15+i*.01,tmax_f:78,tmin_f:60,action:"HOLD",depletion:.35,soil_water:4,gdd:10,et0_in:.2})),history:{},drought:null,outbox:[],planting_window:null,data_as_of:{}
} : []}));
await page.goto(process.env.PREVIEW_URL || 'http://localhost:3000/dashboard');
await page.getByRole('heading',{name:'Your field at a glance'}).waitFor({timeout:15000});
await page.getByRole('heading',{name:'Your growing season'}).waitFor({timeout:3000});
await page.getByRole('button',{name:'Growth diagram',exact:true}).click();
assert.equal(await page.getByTestId('water-dose').innerText(),'3.30 in');
assert.match(await page.getByTestId('growth-value').innerText(),/58%/);
await page.getByLabel('Rotate plant view').fill('90');
await page.getByLabel('Rotate plant view').fill('25');
await page.getByRole('button',{name:'Crop illustration',exact:true}).click();
await page.getByAltText(/Illustration of a maize/).evaluate(img=>img.decode());
assert.equal(await page.getByRole('link',{name:'View field checklist',exact:true}).count(),1);
await page.evaluate(()=>window.scrollTo(0,0));
await page.screenshot({path:'/tmp/plant-dashboard-desktop.png',fullPage:true});
await page.screenshot({path:'/tmp/plant-dashboard-overview.png'});
// Browser zoom reduces the CSS viewport; body.style.zoom does not update media queries.
await page.setViewportSize({width:640,height:360});
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
await page.setViewportSize({width:1280,height:720});
uncertain=true;
await page.reload();
await page.getByRole('heading',{name:'Check your soil first'}).waitFor();
assert.equal(await page.getByTestId('water-dose').count(),0);
growth=null;
await page.reload();
await page.getByText('Growth estimate unavailable',{exact:true}).waitFor();
uncertain=false; growth=8; action='SCHEDULE';
await page.reload();
await page.getByRole('heading',{name:'Plan your next watering'}).waitFor();
assert.match(await page.getByTestId('growth-value').innerText(),/8%/);
uncertain=false; growth=95; action='HOLD';
await page.reload();
await page.getByRole('heading',{name:'No watering today'}).waitFor();
assert.equal(await page.getByTestId('water-dose').count(),0);
await page.setViewportSize({width:360,height:800});
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
await page.getByAltText(/Illustration of a maize/).evaluate(img=>img.decode());
await page.screenshot({path:'/tmp/plant-dashboard-mobile.png',fullPage:true});
console.log('PASS: irrigation, uncertainty, missing growth, hold, schedule, rotation, illustration, checklist and mobile overflow');
} finally {await browser.close();}
