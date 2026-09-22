"use client";

import { useState, useEffect, useRef } from "react";
import PlantStatus from "@/components/PlantStatus";
import { getAdvisory, getCrops, getFarms } from "@/lib/api";
import type { AdvisoryResponse, CropCatalog, Farm, ForecastDay } from "@/lib/types";

const CROP_STORAGE_KEY = "furrowcast_crop";
const PLANTING_STORAGE_KEY = "furrowcast_planting_date";

const FALLBACK_CROPS: string[] = [
  "corn", "soy", "alfalfa", "cover", "potatoes",
  "sunflower", "cabbage", "onions", "sweet corn",
];

function CountySelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const NY_COUNTIES: Array<{ fips: string; name: string }> = [
    { fips: "36001", name: "Albany" },
    { fips: "36003", name: "Allegany" },
    { fips: "36005", name: "Bronx" },
    { fips: "36007", name: "Broome" },
    { fips: "36009", name: "Cattaraugus" },
    { fips: "36011", name: "Cayuga" },
    { fips: "36013", name: "Chautauqua" },
    { fips: "36015", name: "Chemung" },
    { fips: "36017", name: "Chenango" },
    { fips: "36019", name: "Clinton" },
    { fips: "36021", name: "Columbia" },
    { fips: "36023", name: "Cortland" },
    { fips: "36025", name: "Delaware" },
    { fips: "36027", name: "Dutchess" },
    { fips: "36029", name: "Erie" },
    { fips: "36031", name: "Essex" },
    { fips: "36033", name: "Franklin" },
    { fips: "36035", name: "Fulton" },
    { fips: "36037", name: "Genesee" },
    { fips: "36039", name: "Greene" },
    { fips: "36041", name: "Hamilton" },
    { fips: "36043", name: "Herkimer" },
    { fips: "36045", name: "Jefferson" },
    { fips: "36047", name: "Kings" },
    { fips: "36049", name: "Lewis" },
    { fips: "36051", name: "Livingston" },
    { fips: "36053", name: "Madison" },
    { fips: "36055", name: "Monroe" },
    { fips: "36057", name: "Montgomery" },
    { fips: "36059", name: "Nassau" },
    { fips: "36061", name: "New York" },
    { fips: "36063", name: "Niagara" },
    { fips: "36065", name: "Oneida" },
    { fips: "36067", name: "Onondaga" },
    { fips: "36069", name: "Ontario" },
    { fips: "36071", name: "Orange" },
    { fips: "36073", name: "Orleans" },
    { fips: "36075", name: "Oswego" },
    { fips: "36077", name: "Otsego" },
    { fips: "36079", name: "Putnam" },
    { fips: "36081", name: "Queens" },
    { fips: "36083", name: "Rensselaer" },
    { fips: "36085", name: "Richmond" },
    { fips: "36087", name: "Rockland" },
    { fips: "36091", name: "Saratoga" },
    { fips: "36093", name: "Schenectady" },
    { fips: "36095", name: "Schoharie" },
    { fips: "36097", name: "Schuyler" },
    { fips: "36099", name: "Seneca" },
    { fips: "36089", name: "St. Lawrence" },
    { fips: "36101", name: "Steuben" },
    { fips: "36103", name: "Suffolk" },
    { fips: "36105", name: "Sullivan" },
    { fips: "36107", name: "Tioga" },
    { fips: "36109", name: "Tompkins" },
    { fips: "36111", name: "Ulster" },
    { fips: "36113", name: "Warren" },
    { fips: "36115", name: "Washington" },
    { fips: "36117", name: "Wayne" },
    { fips: "36119", name: "Westchester" },
    { fips: "36121", name: "Wyoming" },
    { fips: "36123", name: "Yates" },
  ];
  return (
    <div className="px-4 py-3 bg-transparent">
      <label htmlFor="county" className="block text-sm text-gray-600 mb-2">County (NY)</label>
      <select id="county"
        className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-sm font-sans min-h-[44px] focus:outline-none focus:border-green-500 transition-colors"
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        {NY_COUNTIES.map(c => (
          <option key={c.fips} value={c.fips}>{c.name} NY</option>
        ))}
      </select>
    </div>
  );
}

function FarmConfigPanel({
  crops,
  cropId,
  onCropChange,
  plantingDate,
  onPlantingDateChange,
}: {
  crops: Array<{ id: string }>;
  cropId: string;
  onCropChange: (v: string) => void;
  plantingDate: string;
  onPlantingDateChange: (v: string) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="px-4 py-3 bg-transparent flex flex-col sm:flex-row gap-4">
      <div className="flex-1">
        <label htmlFor="crop" className="block text-sm text-gray-600 mb-2">Your crop</label>
        <select id="crop"
          className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-sm font-sans min-h-[44px] focus:outline-none focus:border-green-500 transition-colors"
          value={cropId}
          onChange={e => onCropChange(e.target.value)}
        >
          {crops.map(c => (
            <option key={c.id} value={c.id}>{c.id.toUpperCase()}</option>
          ))}
        </select>
      </div>
      <div className="flex-1">
        <label htmlFor="planting-date" className="block text-sm text-gray-600 mb-2">Planting date</label>
        <input
          id="planting-date" type="date"
          min="2025-01-01"
          max={today}
          className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-sm font-sans min-h-[44px] focus:outline-none focus:border-green-500 transition-colors"
          value={plantingDate}
          onChange={e => onPlantingDateChange(e.target.value)}
        />
      </div>
    </div>
  );
}

function WeatherIcon({ precip }: { precip: number }) {
  if (precip >= 0.1) {
    return (
      <svg viewBox="0 0 48 48" className="w-10 h-10 mx-auto" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 28a8 8 0 0 1 1.5-15.7A10 10 0 0 1 36 15a7 7 0 0 1-.5 13H15Z" className="text-gray-500" />
        <line x1="17" y1="33" x2="15" y2="39" className="text-blue-500" />
        <line x1="25" y1="33" x2="23" y2="39" className="text-blue-500" />
        <line x1="33" y1="33" x2="31" y2="39" className="text-blue-500" />
      </svg>
    );
  }
  if (precip > 0) {
    return (
      <svg viewBox="0 0 48 48" className="w-10 h-10 mx-auto" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 28a8 8 0 0 1 1.5-15.7A10 10 0 0 1 36 15a7 7 0 0 1-.5 13H15Z" className="text-gray-500" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 48 48" className="w-10 h-10 mx-auto" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="24" cy="24" r="8" className="text-amber-500" />
      <line x1="24" y1="5" x2="24" y2="10" className="text-amber-500" />
      <line x1="24" y1="38" x2="24" y2="43" className="text-amber-500" />
      <line x1="5" y1="24" x2="10" y2="24" className="text-amber-500" />
      <line x1="38" y1="24" x2="43" y2="24" className="text-amber-500" />
      <line x1="11" y1="11" x2="14.5" y2="14.5" className="text-amber-500" />
      <line x1="33.5" y1="33.5" x2="37" y2="37" className="text-amber-500" />
      <line x1="11" y1="37" x2="14.5" y2="33.5" className="text-amber-500" />
      <line x1="33.5" y1="14.5" x2="37" y2="11" className="text-amber-500" />
    </svg>
  );
}

function WeatherStrip({ forecast }: { forecast: ForecastDay[] }) {
  return (
    <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
      <div className="mw-forecast-title"><div><h4>7-Day Forecast</h4><p>Daily weather and crop water outlook</p></div><a href="/weather">View full forecast →</a></div>
      {!forecast || forecast.length === 0 ? (
        <p className="text-gray-500 text-sm font-sans">No forecast data available for this county.</p>
      ) : (
      <div className="mw-forecast-days">
        {forecast.map((day, i) => {
          const dt = new Date(day.date + "T12:00:00");
          const label = i === 0 ? "TODAY" : dt.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
          const dateLabel = dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
          const hasPrecip = day.precip_in > 0;
          const isRain = day.precip_in >= 0.1;
          return (
            <div
              key={day.date}
              className="mw-forecast-day"
            >
              <div className="font-sans text-xs font-semibold tracking-wider text-gray-600">{label}</div>
              <div className="font-sans text-[11px] text-gray-400 mb-1">{dateLabel}</div>
              <WeatherIcon precip={day.precip_in} />
              <div className="font-sans text-sm mt-1">
                <span className="text-gray-800 font-semibold">{Math.round(day.tmax_f)}°</span>
                <span className="text-gray-400"> / {Math.round(day.tmin_f)}°</span>
              </div>
              <div className={`font-sans text-xs mt-1 ${hasPrecip ? (isRain ? "text-blue-600" : "text-gray-500") : "text-gray-300"}`}>
                {hasPrecip ? `${day.precip_in.toFixed(1)}"` : "—"}
              </div>
            </div>
          );
        })}
      </div>
      )}
    </section>
  );
}

function DroughtCard({ drought }: { drought: AdvisoryResponse["drought"] }) {
  const level = (drought?.level ?? null) as string | null;
  const active = !!level && level !== "NONE";
  const SCALE: Record<string, string> = {
    D0: "#FCD34D",
    D1: "#F59E0B",
    D2: "#EF4444",
    D3: "#B91C1C",
    D4: "#7F1D1D",
  };
  const color = !level ? "#94A3B8" : active ? (SCALE[level as string] ?? "#92400E") : "#16A34A";
  return (
    <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h4 className="font-sans text-lg font-semibold text-gray-800 mb-4">Field status</h4>
      <div className="flex items-center gap-3">
        <span
          className="w-5 h-5 rounded-full ring-2 ring-white shadow"
          style={{ backgroundColor: color }}
          aria-hidden
        />
        <div>
          <p className="font-sans text-lg font-bold text-gray-900">
            {!level ? "Drought data unavailable" : active ? `USDM ${level}` : "No active drought"}
          </p>
          <p className="text-sm text-gray-500">
            {!level ? "No drought record was returned for this county" : active ? "Abnormally dry / drought conditions" : "No drought reported in the latest record"}
          </p>
        </div>
      </div>
    </section>
  );
}

function HistoryCard({ history }: { history: AdvisoryResponse["history"] }) {
  const has7d = history?.last_7d_rain != null && history?.last_7d_et != null;
  const has30d =
    history?.july_avg_high != null && history?.july_avg_low != null && history?.july_total_rain != null;
  return (
    <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h4 className="font-sans text-lg font-semibold text-gray-800 mb-4">WEATHER HISTORY</h4>
      {has7d ? (
        <p className="font-sans text-xl font-bold text-gray-900">
          Past 7 days: {history.last_7d_rain.toFixed(1)} in rain, {history.last_7d_et.toFixed(1)} in ET
        </p>
      ) : (
        <p className="font-sans text-xl font-bold text-gray-500">Setting up data for this county</p>
      )}
      {has30d ? (
        <p className="text-sm text-gray-500 mt-2">
          30-day avg high {Math.round(history.july_avg_high)}° / low {Math.round(history.july_avg_low)}° ·{" "}
          {history.july_total_rain.toFixed(1)}&quot; total rain
        </p>
      ) : (
        <p className="text-sm text-gray-500 mt-2">No historical record available</p>
      )}
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <main className="min-h-screen bg-[#f5f6f0]">
      <div className="border-b border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <p role="status" className="text-sm text-gray-600">Loading your field and weather data…</p>
          <div className="h-7 w-40 bg-gray-200 rounded mt-2 animate-pulse" />
        </div>
      </div>
      <div className="max-w-7xl mx-auto px-6 py-8">
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 mb-8">
          <div className="h-3 w-40 bg-gray-200 rounded animate-pulse mb-4" />
          <div className="h-10 w-80 bg-gray-200 rounded animate-pulse" />
          <div className="mt-6 flex gap-4">
            <div className="h-10 w-24 bg-gray-200 rounded-full animate-pulse" />
          </div>
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-gray-50 border border-gray-200 rounded-lg p-3 h-16 animate-pulse" />
            ))}
          </div>
        </section>
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="h-4 w-40 bg-gray-200 rounded animate-pulse mb-4" />
          <div className="flex gap-3 overflow-hidden">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="flex-none w-28 h-36 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

export default function DashboardPage() {
  const [selectedCounty, setSelectedCounty] = useState("36037");
  const [advisory, setAdvisory] = useState<AdvisoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectionReady, setSelectionReady] = useState(false);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [cropsCatalog, setCropsCatalog] = useState<CropCatalog[]>([]);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [cropId, setCropId] = useState("corn");
  const [plantingDate, setPlantingDate] = useState("");
  const autoSetPlantingRef = useRef(false);
  const loadedSelectionRef = useRef("");
  // Restore last selection + load the Crop Library and the user's farms
  useEffect(() => {
    setSelectedCounty(localStorage.getItem("furrowcast_county") || "36037");
    setCropId(localStorage.getItem(CROP_STORAGE_KEY) || "corn");
    setPlantingDate(localStorage.getItem(PLANTING_STORAGE_KEY) || "");
    setSelectionReady(true);

    let mounted = true;
    getCrops().then(rows => {
      if (mounted && rows.length > 0) setCropsCatalog(rows);
    });
    getFarms().then(rows => {
      if (mounted) setFarms(rows);
    });
    return () => {
      mounted = false;
    };
  }, []);

  // Persist the selection — "this is what my farm is planted to"
  useEffect(() => {
    if (!selectionReady) return;
    localStorage.setItem(CROP_STORAGE_KEY, cropId);
    localStorage.setItem(PLANTING_STORAGE_KEY, plantingDate);
  }, [cropId, plantingDate, selectionReady]);

  // Prefill from the user's farm for the selected county
  useEffect(() => {
    const farm = farms.find(f => f.county_fips === selectedCounty);
    if (farm && farm.crops.length > 0) {
      const primary = farm.crops[0];
      setCropId(primary.crop_id);
      if (primary.planting_date) setPlantingDate(primary.planting_date);
    }
  }, [selectedCounty, farms]);

  useEffect(() => {
    if (!selectionReady) return;
    const selectionKey = JSON.stringify([selectedCounty, cropId, plantingDate, reloadKey]);
    if (loadedSelectionRef.current === selectionKey) return;
    const controller = new AbortController();
    let mounted = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getAdvisory(selectedCounty, { cropId, plantingDate, signal: controller.signal });
        if (mounted) {
          loadedSelectionRef.current = JSON.stringify([selectedCounty, cropId, plantingDate || data?.crop?.planting_date || "", reloadKey]);
          setAdvisory(data);
        }
      } catch (e: any) {
        if (controller.signal.aborted) return;
        if (e.message === "UNAUTHENTICATED") {
          window.location.href = "/login";
          return;
        }
        if (mounted) setError(e.message || "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [selectedCounty, cropId, plantingDate, reloadKey, selectionReady]);

  // Once the backend reports the effective planting date, surface it in the picker
  useEffect(() => {
    if (advisory && advisory.crop && !plantingDate && advisory.crop.planting_date && !autoSetPlantingRef.current) {
      autoSetPlantingRef.current = true;
      setPlantingDate(advisory.crop.planting_date);
    }
  }, [advisory, plantingDate]);

  const cropOptions = cropsCatalog.length > 0 ? cropsCatalog.map(c => ({ id: c.id })) : FALLBACK_CROPS.map(id => ({ id }));

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <main className="min-h-screen bg-[#f5f6f0]">
        <div className="max-w-7xl mx-auto px-4 py-12 text-center">
          <p className="font-sans text-xl text-red-600 mb-2">Something went wrong</p>
          <p className="text-gray-600 text-sm mb-6">{error}</p>
            <button
              onClick={() => setReloadKey((k) => k + 1)}
              className="mt-4 px-6 py-2 min-h-[44px] bg-green-600 text-white font-sans text-sm rounded-lg hover:bg-green-700 transition-colors"
            >
              RETRY
            </button>
        </div>
      </main>
    );
  }

  if (!advisory || !advisory.today) {
    return (
      <main className="min-h-screen bg-[#f5f6f0]">
        <div className="max-w-7xl mx-auto px-4 py-12 text-center">
          <p className="font-sans text-sm text-gray-500">Data unavailable for this county</p>
        </div>
      </main>
    );
  }

  const { forecast, county, drought, history, planting_window, outbox } = advisory;

  const pipelineAt = advisory.data_as_of?.last_pipeline_at;
  const dataAsOf = pipelineAt
    ? new Date(pipelineAt.replace(" ", "T")).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <main className="mw-reference-dashboard">
      <PlantStatus advisory={advisory} filters={<div className="mw-reference-filters">
        <CountySelector value={selectedCounty} onChange={value=>{setSelectedCounty(value);localStorage.setItem("furrowcast_county",value);}} />
        <FarmConfigPanel crops={cropOptions} cropId={cropId} onCropChange={setCropId} plantingDate={plantingDate} onPlantingDateChange={setPlantingDate} />
        <button className="mw-reference-update" onClick={()=>setReloadKey(k=>k+1)}>Update</button>
      </div>} />
      <div className="mw-reference-lower">
        <div><WeatherStrip forecast={forecast}/><details className="mw-reference-history"><summary>Weather history & data freshness</summary><p>Data as of {dataAsOf || "unavailable"} · {county.name}, {county.state}</p><HistoryCard history={history}/></details></div>
        <div className="mw-reference-status">
            <DroughtCard drought={drought} />

            <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h4 className="font-sans text-lg font-semibold text-gray-800 mb-4">Planting window</h4>
              {planting_window ? (
                <div className="space-y-3">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="font-sans text-xs text-gray-500 uppercase tracking-wider mb-1">FROST 50%</p>
                    <p className="font-sans text-lg font-bold text-gray-800">
                      {planting_window.frost_50pct}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="font-sans text-xs text-gray-500 uppercase tracking-wider mb-1">LATEST SAFE PLANT</p>
                    <p className="font-sans text-lg font-bold text-gray-800">
                      {planting_window.corn_start}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-sm">Planting window data not available</p>
              )}
            </section>

            <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h4 className="font-sans text-lg font-semibold text-gray-800 mb-4">Recent advisories</h4>
              {outbox.length === 0 ? (
                <p className="text-gray-500 text-sm">No advisories sent yet.</p>
              ) : (
                <div className="space-y-2">
                  {outbox.slice(0, 3).map((o, i) => (
                    <div key={i} className="flex justify-between items-center border-b border-gray-200 pb-2 last:border-0">
                      <span className="font-sans text-xs tracking-wider text-gray-500">
                        {new Date(o.sent_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
                        })}
                      </span>
                      <span className="font-sans text-xs tracking-wider text-gray-500 max-w-xs truncate">{o.body}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </div>
    </main>
  );
}
