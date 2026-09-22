"use client";
import {useEffect,useState} from "react";
import {getAdvisory} from "./api";
import type {AdvisoryResponse} from "./types";
export const defaults={name:'',units:'in',temperature:'F',area:'acres',reminders:true};
export function useLocalData<T>(key:string,initial:T){
 const[value,setValue]=useState<T>(initial);const[ready,setReady]=useState(false);const[error,setError]=useState('');
 useEffect(()=>{try{const raw=localStorage.getItem(key);if(raw)setValue(JSON.parse(raw));}catch{setError('Saved browser data could not be read.');}setReady(true);},[key]);
 const save=(next:T)=>{try{localStorage.setItem(key,JSON.stringify(next));setValue(next);setError('');return true;}catch{setError('Browser storage is full or unavailable. Your changes were not saved.');return false;}};
 return {value,save,ready,error};
}
export function useAdvisoryData(){
 const[data,setData]=useState<AdvisoryResponse|null>(null);const[loading,setLoading]=useState(true);const[error,setError]=useState('');const[retry,setRetry]=useState(0);
 useEffect(()=>{const c=new AbortController();setLoading(true);setError('');getAdvisory(localStorage.getItem('furrowcast_county')||'36037',{cropId:localStorage.getItem('furrowcast_crop')||'corn',plantingDate:localStorage.getItem('furrowcast_planting_date')||'',signal:c.signal}).then(d=>{if(c.signal.aborted)return;if(d)setData(d as AdvisoryResponse);else setError('Advisory data is unavailable. Check your connection or try another county from Overview.');}).catch(e=>{if(c.signal.aborted)return;if(e.message==='UNAUTHENTICATED')window.location.href='/login';else setError('Could not load your field data.');}).finally(()=>{if(!c.signal.aborted)setLoading(false);});return()=>c.abort();},[retry]);
 return{data,loading,error,reload:()=>setRetry(x=>x+1)};
}
export const number=(n:unknown,digits=1)=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(digits):'—';
export function downloadFile(name:string,content:string,type:string){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

export function localDateString(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
