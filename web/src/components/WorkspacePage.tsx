"use client";
import { defaults,useAdvisoryData,useLocalData } from "@/lib/workspace";
import Link from "next/link";
import { navigation } from "./AppShell";
import Checklist from "./workspace/Checklist";
import { Empty } from "./workspace/DataViews";
import Growth from "./workspace/Growth";
import Help from "./workspace/Help";
import Journal from "./workspace/Journal";
import Reports from "./workspace/Reports";
import Settings from "./workspace/Settings";
import Water from "./workspace/Water";
import Weather from "./workspace/Weather";
const descriptions:Record<string,string>={growth:'Follow your crop’s development, from the first leaves to estimated maturity.',water:'Understand the balance between rainfall, crop water use and soil reserves.',journal:'Keep your field observations together, one growing day at a time.',weather:'A clearer look at the conditions shaping your week.',reports:'Turn your current field estimates into useful, shareable records.',settings:'Make this workspace work for you.',checklist:'A few thoughtful checks before your next irrigation decision.',help:'Get to know your data, your tools and your next steps.'};
function DataPage({section}:{section:string}){const{data,loading,error,reload}=useAdvisoryData();const prefs=useLocalData('muons_preferences',defaults);const unit=prefs.value.units==='mm'?'mm':'in';if(loading)return <div className="mw-card" role="status">Loading your field data…</div>;if(error||!data)return <div className="mw-card"><Empty title="Your field data is unavailable" body={error||'No advisory was returned.'}/><button className="mw-btn mt-5" onClick={reload}>Retry</button><Link href="/dashboard" className="mw-btn secondary ml-3">Change selection</Link></div>;return <><div className="mw-row justify-between mb-6"><span className="mw-local">{data.county.name}, {data.county.state} · {data.crop.id} · {unit}</span><Link className="text-sm text-green-800" href="/dashboard">Change field selection →</Link></div>{prefs.value.reminders&&section!=='reports'&&<div className="mw-note">Before acting, compare the estimate with your field. <Link className="underline" href="/checklist">Open field checklist</Link>.</div>}{section==='growth'?<Growth data={data} unit={unit}/>:section==='water'?<Water data={data} unit={unit}/>:section==='weather'?<Weather data={data} unit={unit}/>:<Reports data={data} unit={unit}/>}</>;}
export default function WorkspacePage({section}:{section:string}){const title=section==='growth'?'Crop Growth':navigation.find(n=>n[0]===`/${section}`)?.[1]||section;return <main className="mw-page"><header className="mw-page-head"><div><span className="mw-eyebrow">MUONS WATER / YOUR WORKSPACE</span><h1>{title}</h1><p>{descriptions[section]}</p></div>{['journal','settings','checklist'].includes(section)&&<span className="mw-local">Stored on this browser</span>}</header>{section==='journal'?<Journal/>:section==='settings'?<Settings/>:section==='checklist'?<Checklist/>:section==='help'?<Help/>:<DataPage section={section}/>}</main>;}
