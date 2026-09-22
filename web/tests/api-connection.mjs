import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const js=ts.transpileModule(fs.readFileSync(new URL('../src/lib/api.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
function api(host,env={},fetch=async()=>({ok:true,json:async()=>({})})) { const exports={};vm.runInNewContext(js,{exports,window:{location:{hostname:host}},process:{env},fetch,URLSearchParams,DOMException,Error,console});return exports; }
assert.equal(api('127.0.0.1').apiBaseUrl(),'http://127.0.0.1:8000');
assert.equal(api('localhost').apiBaseUrl(),'http://localhost:8000');
assert.equal(api('127.0.0.1',{NEXT_PUBLIC_API_PORT:'8003'}).apiBaseUrl(),'http://127.0.0.1:8003');
assert.equal(api('127.0.0.1',{NEXT_PUBLIC_API_URL:'https://api.example.com'}).apiBaseUrl(),'https://api.example.com');
await assert.rejects(api('127.0.0.1',{},async()=>{throw new Error('Offline');}).getAdvisory('36037'),/Cannot reach the data service/);
await assert.rejects(api('127.0.0.1',{},async()=>({ok:false,status:401})).getAdvisory('36037'),/UNAUTHENTICATED/);
await assert.rejects(api('127.0.0.1',{},async()=>({ok:false,status:502})).getAdvisory('36037'),/Advisory service returned 502/);
console.log('PASS: same-host API, selected ports, overrides, network/HTTP errors, auth redirect signal');
