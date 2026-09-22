import {notFound} from "next/navigation";
import WorkspacePage from "@/components/WorkspacePage";
const pages=['growth','water','journal','weather','reports','settings','checklist','help'];
export function generateStaticParams(){return pages.map(section=>({section}));}
export default function Page({params}:{params:{section:string}}){if(!pages.includes(params.section))notFound();return <WorkspacePage section={params.section}/>;}
