"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { AdvisoryResponse } from "@/lib/types";
import styles from "./PlantStatus.module.css";

type Point = [number, number, number];
const percent = (n: number) => Math.max(0, Math.min(100, n));
const known = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);
const amount = (n: number) => known(n) ? n.toFixed(2) : "—";

/** Orthographic 3D data diagram. Geometry is schematic, never measured plant height. */
function PlantView({ growth, angle, crop }: { growth: number | null; angle: number; crop: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const scale = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = 560 * scale; canvas.height = 400 * scale;
    ctx.scale(scale, scale);
    const a = angle * Math.PI / 180;
    const rotate = ([x,y,z]: Point): Point => [x*Math.cos(a)-z*Math.sin(a),y,x*Math.sin(a)+z*Math.cos(a)];
    const project = (p: Point): [number,number] => { const [x,y,z]=rotate(p); return [280+x,300-y+z*.38]; };
    const faces: {points: Point[]; color: string}[] = [];
    const face = (points: Point[], color: string) => faces.push({points,color});
    const top: Point[] = [[-100,0,-75],[100,0,-75],[100,0,75],[-100,0,75]];
    face(top,"#927548");
    for(let i=0;i<4;i++) { const p=top[i], q=top[(i+1)%4]; face([p,q,[q[0],-48,q[2]],[p[0],-48,p[2]]],i%2?"#785032":"#62412b"); }
    // Soil faces first; rotate the plant independently through the same projection.
    const drawFaces = () => {
      faces.sort((f,g)=>f.points.reduce((s,p)=>s+rotate(p)[2],0)/f.points.length-g.points.reduce((s,p)=>s+rotate(p)[2],0)/g.points.length);
      for(const f of faces){ctx.beginPath(); f.points.forEach((p,i)=>{const [x,y]=project(p);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.closePath();ctx.fillStyle=f.color;ctx.fill();}
      faces.length=0;
    };
    ctx.fillStyle="#c8d2b9";ctx.beginPath();ctx.ellipse(280,350,135,21,0,0,Math.PI*2);ctx.fill();
    drawFaces();
    if(growth===null) return;
    const leafy = ["cabbage","potatoes","soy","alfalfa","cover"].includes(crop);
    const h = 35 + growth * (leafy ? 1.35 : 2.15);
    const line = (p: Point,q: Point,width:number,color:string) => {const from=project(p),to=project(q);ctx.beginPath();ctx.moveTo(...from);ctx.lineTo(...to);ctx.lineWidth=width;ctx.strokeStyle=color;ctx.lineCap="round";ctx.stroke();};
    line([0,0,0],[0,h,0],7,"#477430");
    const leaves = 2+Math.floor(growth/12);
    for(let i=0;i<leaves;i++){
      const yaw=i*2.4, y=12+(i/(leaves+1))*h*.88;
      const length=(leafy?75:87)*(0.42+growth/170)*(1-i/(leaves*1.8));
      const width=leafy?25:13;
      const p:Point=[0,y,0];
      const tip:Point=[Math.cos(yaw)*length,y+length*.3,Math.sin(yaw)*length];
      const mid:Point=[tip[0]*.55,y+length*.42,tip[2]*.55];
      face([p,[mid[0]+Math.sin(yaw)*width,mid[1],mid[2]-Math.cos(yaw)*width],tip],"#4e8a35");
      face([p,tip,[mid[0]-Math.sin(yaw)*width,mid[1],mid[2]+Math.cos(yaw)*width]],"#80ae4e");
    }
    drawFaces();
    if(growth>=50 && (crop==='corn'||crop==='sweet corn'||crop==='sunflower')){
      for(let i=-2;i<=2;i++)line([0,h-5,0],[i*6,h+15-Math.abs(i)*4,i*3],3,"#bba052");
    }
  }, [growth,angle,crop]);
  return <canvas ref={ref} className={styles.canvas} aria-hidden="true" />;
}

type IconName = "leaf" | "water" | "rain" | "sun" | "check" | "arrow" | "layers";
function Icon({ name, className }: { name: IconName; className?: string }) {
  const paths: Record<IconName,string> = {
    leaf: "M20 4C10 2 3 7 5 15c2 8 15 6 15-11ZM5 21 15 11",
    water: "M12 3C10 7 5 12 5 16a7 7 0 0 0 14 0c0-4-5-9-7-13ZM8 16c0 2 1 3 3 3",
    rain: "M5 14a4 4 0 0 1 0-8 6 6 0 0 1 11-1 4.5 4.5 0 0 1 2 9M7 17l-1 3m7-3-1 3m7-3-1 3",
    sun: "M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1M16 12a4 4 0 1 0-8 0 4 4 0 0 0 8 0",
    check: "m5 12 4 4L19 6",
    arrow: "M4 12h16m-6-6 6 6-6 6",
    layers: "m12 3 10 6-10 6L2 9l10-6ZM2 14l10 6 10-6",
  };
  return <svg className={className} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

export default function PlantStatus({ advisory, filters }: { advisory: AdvisoryResponse; filters?: ReactNode }) {
  const {crop,today,soil,forecast} = advisory;
  const [angle,setAngle] = useState(25);
  const [view,setView] = useState<"illustration"|"diagram">("illustration");
  const growth = known(crop.gdd_pct) ? percent(crop.gdd_pct) : null;
  const moisture = known(today.soil_pct) ? percent(today.soil_pct) : null;
  const uncertain = today.advice_uncertain || soil.water_source === "assumed" || moisture === null;
  const irrigate = !uncertain && today.action === "IRRIGATE";
  const title = uncertain ? "Check your soil first" : irrigate ? "Time to water" : today.action === "SCHEDULE" ? "Plan your next watering" : "No watering today";
  const message = uncertain ? "Starting moisture is uncertain. Check moisture in the root zone before deciding how much to water." : irrigate ? "Your estimated soil water has reached the refill point. Check field conditions before applying water." : today.action === "SCHEDULE" ? "Soil water is forecast to run low. Prepare to irrigate and check the next update." : "The model does not call for irrigation today. Check again as weather and field conditions change.";
  const refill = known(crop.mad) ? Math.round((1-crop.mad)*100) : null;
  const days = forecast.slice(0,7);
  const chartMax = Math.max(.1,...days.flatMap(d=>[known(d.precip_in)?d.precip_in:0,known(d.etc)?d.etc:0]));
  const stages = [{label:"Early growth",at:0},{label:"Reproductive",at:50},{label:"Filling",at:62},{label:"Maturity",at:90}];
  const active = growth===null ? -1 : stages.reduce((last,stage,i)=>growth>=stage.at?i:last,0);

  return <section className={styles.dashboard} aria-labelledby="field-heading" id="field-overview">
    <header className={styles.heading}><div className={styles.headingText}><h1 id="field-heading">Your field at a glance</h1><p>Better insights. Smarter decisions. A more productive tomorrow.</p></div><div className={styles.heroMark}><Icon name="leaf"/><span>Healthy Fields<br/>Sustainable Futures</span></div>{filters}</header>
    <div className={styles.spotlightRow}>
      <section className={styles.plant}>
        {view==='illustration'?<Image src="/images/crop-spotlight.png" alt="Illustration of a maize plant in soil, not a measurement of your crop." fill sizes="(max-width: 800px) 100vw, 600px" priority className={styles.art}/>:<div className={styles.diagram}><PlantView growth={growth} angle={angle} crop={crop.id}/></div>}
        <span className={styles.stagePill}><Icon name="leaf"/>{crop.stage_label||'Stage unavailable'}</span>
        <div className={styles.cropCopy}><span className={styles.kicker}>Crop Spotlight</span><h2>{crop.id}</h2><p className={styles.botanical}>{['corn','sweet corn'].includes(crop.id)?'Zea mays':'Your selected crop'}</p><ul className={styles.cropFacts}><li><Icon name="sun"/><span>{crop.planting_date?`Planted ${crop.planting_date}`:'Planting date unavailable'}</span></li><li><Icon name="leaf"/><span data-testid="growth-value">{growth===null?'Growth estimate unavailable':`${Math.round(growth)}% estimated growth`}</span></li><li><Icon name="water"/><span>{uncertain?'Check starting moisture':'Modelled water needs'}</span></li></ul><a className={styles.cropButton} href="/growth">View growth stages <Icon name="arrow"/></a></div>
        <div className={styles.viewControls}><button type="button" onClick={()=>setView(view==='diagram'?'illustration':'diagram')}>{view==='diagram'?'Crop illustration':'Growth diagram'}</button>{view==='diagram'&&<label>Rotate plant view<input aria-label="Rotate plant view" type="range" min="-180" max="180" value={angle} onChange={e=>setAngle(Number(e.target.value))}/></label>}<small>Illustrative crop · model estimates</small></div>
      </section>
      <article className={`${styles.action} ${uncertain?styles.check:''}`}><div className={styles.actionTop}><span><i><Icon name="water"/></i>Your Next Move</span><Icon name={uncertain?'layers':'water'}/></div><h2>{title}</h2><p>{message}</p>{irrigate&&known(today.irrigate_amount)&&today.irrigate_amount>0?<div className={styles.dose}><strong data-testid="water-dose">{amount(today.irrigate_amount)} in</strong><span>Estimated irrigation depth<br/>{(today.irrigate_amount*25.4).toFixed(0)} mm over the field</span></div>:<div className={styles.actionHint}>{uncertain?'Resolve uncertainty before choosing a dose.':'Keep an eye on soil and weather conditions.'}</div>}<a className={styles.actionButton} href="/checklist">View field checklist <Icon name="arrow"/></a><div className={styles.actionFoot}>ⓘ &nbsp; Based on the water-budget model</div></article>
    </div>
    <div className={styles.metrics}><article><span className={`${styles.metricIcon} ${styles.blue}`}><Icon name="water"/></span><div><span>Crop water use today</span><strong>{amount(today.etc)} <small>in</small></strong><p>Water use, not an irrigation amount</p></div></article><article><span className={`${styles.metricIcon} ${styles.blue}`}><Icon name="rain"/></span><div><span>Rain in the next 7 days</span><strong>{amount(today.rain_7d)} <small>in</small></strong><p>Forecast rainfall</p></div></article><article><span className={styles.metricIcon}><Icon name="leaf"/></span><div><span>Soil water remaining</span><strong>{moisture===null?'—':`${Math.round(moisture)}%`}</strong><div className={styles.waterTrack} role="meter" aria-label="Estimated soil water remaining" aria-valuemin={0} aria-valuemax={100} aria-valuenow={moisture??undefined}><span style={{width:`${moisture??0}%`}}/></div><p className={styles.refill}>Refill line: {refill??'—'}%</p></div></article></div>
    <div className={styles.seasonRow}><section className={styles.season} id="growing-season"><span className={styles.kicker}>From planting to maturity</span><h2>Your growing season</h2><div className={styles.timeline}>{stages.map((stage,i)=><div key={stage.label} className={`${styles.milestone} ${i===active?styles.current:''} ${i<active?styles.past:''}`} aria-current={i===active?'step':undefined}><span className={styles.stageNumber}><Icon name={i<active?'check':'leaf'}/></span><strong>{stage.label}</strong><small>{stage.at}% of heat target</small>{i===active&&<span className={styles.youAreHere}>Current stage</span>}</div>)}</div><div className={styles.seasonFoot}><p><Icon name="leaf"/><span>Heat accumulation estimates development.<small>It does not measure plant height or confirm harvest readiness.</small></span></p><a href="/growth">View growth details <Icon name="arrow"/></a></div></section><section className={styles.range}><div className={styles.rangeTitle}><span className={styles.metricIcon}><Icon name="layers"/></span><div><span>Possible soil water range</span><strong>{known(today.soil_min_pct)&&known(today.soil_max_pct)?`${Math.round(today.soil_min_pct)} – ${Math.round(today.soil_max_pct)}%`:'Unknown'}</strong><p>Starting-moisture uncertainty only</p></div></div><div className={styles.rangeGraphic} aria-label="Starting-moisture uncertainty interval"><div className={styles.rangeRail}>{known(today.soil_min_pct)&&known(today.soil_max_pct)&&<span style={{left:`${percent(today.soil_min_pct)}%`,width:`${Math.max(1,percent(today.soil_max_pct)-percent(today.soil_min_pct))}%`}}/>}{moisture!==null&&<i style={{left:`${moisture}%`}}/>}</div><div className={styles.rangeAxis}><span>0%</span><span>Available soil water</span><span>100%</span></div><p>Today’s possible range, not a measured trend.</p></div></section></div>
    <div className={styles.education} id="water-outlook"><section className={styles.outlook}><div className={styles.sectionHeading}><div><span className={styles.kicker}>This week’s outlook</span><h2>Water in. Water out.</h2></div><a href="/water">Daily <Icon name="arrow"/></a></div><p className={styles.intro}>Compare forecast rain with the water your crop is expected to use.</p>{days.length?<><div className={styles.legend}><span><i/>Rainfall</span><span><i/>Crop water use</span></div><span className={styles.axisLabel}>Inches / day</span><div className={styles.chart}><div className={styles.yAxis}>{[1,.66,.33,0].map(n=><span key={n}>{(chartMax*n).toFixed(2)}</span>)}</div><div className={styles.plot}>{days.map(d=><div className={styles.day} key={d.date}><div className={styles.bars}><div title={`${d.date}: ${amount(d.precip_in)} in rainfall`} style={{height:`${known(d.precip_in)?Math.max(1,d.precip_in/chartMax*100):0}%`}}><span>{amount(d.precip_in)}</span></div><div title={`${d.date}: ${amount(d.etc)} in crop use`} style={{height:`${known(d.etc)?Math.max(1,d.etc/chartMax*100):0}%`}}><span>{amount(d.etc)}</span></div></div><strong>{new Date(`${d.date}T12:00:00`).toLocaleDateString('en-US',{weekday:'short'})}</strong><small>{new Date(`${d.date}T12:00:00`).toLocaleDateString('en-US',{month:'short',day:'numeric'})}</small></div>)}</div></div></>:<div className={styles.empty}><Icon name="rain"/><strong>No forecast data available</strong><p>The daily chart will appear when forecasts are available.</p></div>}</section><section className={styles.explainer}><div className={styles.explainerTitle}><Icon name="sun"/><div><span className={styles.kicker}>Make sense of the numbers</span><h2>Why this advice?</h2></div></div>{[['Start with the soil',`The model estimates ${moisture===null?'unknown moisture':`${Math.round(moisture)}% soil water remains`}. The refill line is ${refill??'unknown'}${refill===null?'':'%'}.`],['Account for the crop',`Estimated crop water use is ${amount(today.etc)} inches today. This is separate from the amount to irrigate.`],['Check the confidence',uncertain?'Unknown starting moisture can change the decision. Check actual soil before acting.':'The starting-moisture range does not change today’s model action. Weather and model error still remain.']].map(([label,body],i)=><div className={styles.reason} key={label}><span>0{i+1}</span><div><strong>{label}</strong><p>{body}</p></div></div>)}</section></div>
  </section>;
}
