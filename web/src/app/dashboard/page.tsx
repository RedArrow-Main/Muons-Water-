"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAdvisory, logout } from "@/lib/api";
import type { AdvisoryResponse, ForecastDay } from "@/lib/types";

const TODAY = new Date().toLocaleDateString("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
});

function DecisionBadge({ action }: { action: string }) {
  const colors = {
    HOLD: { bg: "bg-green-100", text: "text-green-900", border: "border-green-300", label: "HOLD" },
    SCHEDULE: { bg: "bg-amber-100", text: "text-amber-900", border: "border-amber-300", label: "SCHEDULE" },
    IRRIGATE: { bg: "bg-red-100", text: "text-red-900", border: "border-red-300", label: "IRRIGATE" },
  };
  const c = colors[action as keyof typeof colors] || colors.HOLD;
  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border-2 ${c.border} ${c.bg} ${c.text}`}>
      <span className="font-mono text-xs font-bold tracking-wider">{c.label}</span>
    </div>
  );
}

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
    <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
      <label className="block text-xs font-mono text-gray-500 mb-2 tracking-wider">SELECT COUNTY (NY)</label>
      <select
        className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-sm font-mono min-h-[44px] focus:outline-none focus:border-green-500 transition-colors"
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

function SoilGauge({ pct }: { pct: number }) {
  const clamped = Math.min(100, Math.max(0, pct));
  const color = clamped >= 60 ? "text-green-500" : clamped >= 40 ? "text-amber-500" : "text-red-500";
  return (
    <div className="text-center">
      <div className="relative w-32 h-32 mx-auto mb-2">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="8" className="text-gray-200" />
          <circle
            cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="8"
            className={color}
            strokeDasharray={`${clamped * 2.64} 264`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`font-mono text-3xl font-bold ${color}`}>{Math.round(clamped)}%</span>
        </div>
      </div>
      <div>
        <span className="font-mono text-sm text-gray-600 block">Soil water</span>
        <span className="font-mono text-[10px] text-gray-500 -mt-1">How wet the root zone is</span>
      </div>
    </div>
  );
}

function SimpleMetric({ label, value, subtext, unit }: { label: string; value: string | number; subtext?: string; unit?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <small className="font-mono text-[8.5px] tracking-[0.16em] text-gray-500 block mb-1">{label}</small>
      <b className="font-mono text-lg">
        {value}
        {unit && <span className="font-mono text-[10px] text-gray-400 ml-1">{unit}</span>}
      </b>
      {subtext && (
        <small className="font-mono text-[8.5px] tracking-[0.16em] text-gray-400 block -mt-1">{subtext}</small>
      )}
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
      <h4 className="font-mono text-lg font-semibold text-gray-800 mb-4">7-DAY FORECAST</h4>
      {!forecast || forecast.length === 0 ? (
        <p className="text-gray-500 text-sm font-mono">No forecast data available for this county.</p>
      ) : (
      <div className="flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory">
        {forecast.map((day, i) => {
          const dt = new Date(day.date + "T12:00:00");
          const label = i === 0 ? "TODAY" : dt.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
          const dateLabel = dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
          const hasPrecip = day.precip_in > 0;
          const isRain = day.precip_in >= 0.1;
          return (
            <div
              key={day.date}
              className="flex-none w-28 snap-center border border-gray-200 rounded-xl p-3 text-center hover:border-green-300 transition-colors"
            >
              <div className="font-mono text-xs font-semibold tracking-wider text-gray-600">{label}</div>
              <div className="font-mono text-[11px] text-gray-400 mb-1">{dateLabel}</div>
              <WeatherIcon precip={day.precip_in} />
              <div className="font-mono text-sm mt-1">
                <span className="text-gray-800 font-semibold">{Math.round(day.tmax_f)}°</span>
                <span className="text-gray-400"> / {Math.round(day.tmin_f)}°</span>
              </div>
              <div className={`font-mono text-xs mt-1 ${hasPrecip ? (isRain ? "text-blue-600" : "text-gray-500") : "text-gray-300"}`}>
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
  const color = active ? (SCALE[level as string] ?? "#92400E") : "#16A34A";
  return (
    <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h4 className="font-mono text-lg font-semibold text-gray-800 mb-4">DROUGHT STATUS</h4>
      <div className="flex items-center gap-3">
        <span
          className="w-5 h-5 rounded-full ring-2 ring-white shadow"
          style={{ backgroundColor: color }}
          aria-hidden
        />
        <div>
          <p className="font-mono text-lg font-bold text-gray-900">
            {active ? `USDM ${level}` : "No active drought"}
          </p>
          <p className="text-sm text-gray-500">
            {active ? "Abnormally dry / drought conditions" : "Conditions normal for this county"}
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
      <h4 className="font-mono text-lg font-semibold text-gray-800 mb-4">WEATHER HISTORY</h4>
      {has7d ? (
        <p className="font-mono text-xl font-bold text-gray-900">
          Past 7 days: {history.last_7d_rain.toFixed(1)} in rain, {history.last_7d_et.toFixed(1)} in ET
        </p>
      ) : (
        <p className="font-mono text-xl font-bold text-gray-500">Setting up data for this county</p>
      )}
      {has30d ? (
        <p className="text-sm text-gray-500 mt-2">
          30-day avg high {Math.round(history.july_avg_high)}° / low {Math.round(history.july_avg_low)}° ·{" "}
          {history.july_total_rain.toFixed(1)}" total rain
        </p>
      ) : (
        <p className="text-sm text-gray-500 mt-2">No historical record available</p>
      )}
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="border-b border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="h-5 w-32 bg-gray-200 rounded animate-pulse" />
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const router = useRouter();

  async function handleLogout() {
    try {
      await logout();
    } catch {
      /* ignore network errors — still redirect */
    }
    router.push("/login");
  }

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getAdvisory(selectedCounty, controller.signal);
        if (mounted) setAdvisory(data);
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
  }, [selectedCounty, reloadKey]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 py-12 text-center">
          <p className="font-mono text-xl text-red-600 mb-2">Something went wrong</p>
          <p className="text-gray-600 text-sm mb-6">{error}</p>
            <button
              onClick={() => setReloadKey((k) => k + 1)}
              className="mt-4 px-6 py-2 min-h-[44px] bg-green-600 text-white font-mono text-sm rounded-lg hover:bg-green-700 transition-colors"
            >
              RETRY
            </button>
        </div>
      </main>
    );
  }

  if (!advisory || !advisory.today) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 py-12 text-center">
          <p className="font-mono text-sm text-gray-500">Data unavailable for this county</p>
        </div>
      </main>
    );
  }

  const { today, forecast, county, soil, crop, drought, history, planting_window, outbox } = advisory;

  const actionLabel =
    today.action === "HOLD"
      ? "HOLD — NO IRRIGATION NEEDED TODAY"
      : today.action === "SCHEDULE"
      ? "SCHEDULE — LOW MOISTURE FORECAST"
      : "IRRIGATE — RUN PIVOT TODAY";

  const actionColor =
    today.action === "IRRIGATE"
      ? "text-red-700"
      : today.action === "SCHEDULE"
      ? "text-amber-700"
      : "text-green-700";

  const pipelineAt = advisory.data_as_of?.last_pipeline_at;
  const dataAsOf = pipelineAt
    ? new Date(pipelineAt.replace(" ", "T")).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="border-b border-gray-200 bg-white/95 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="font-mono text-xl font-bold text-green-800 tracking-wide">MUONS WATER</h1>
            <h2 className="font-mono text-2xl text-gray-800 font-semibold mt-1">
              {county.name}, {county.state}
            </h2>
            {dataAsOf && (
              <p className="font-mono text-[11px] text-gray-400 mt-1 tracking-wide">
                Data as of {dataAsOf}
              </p>
            )}
          </div>
          <div className="text-right flex items-center gap-3">
            <p className="font-mono text-sm text-gray-500 tracking-wider">{TODAY}</p>
            <button
              onClick={handleLogout}
              className="px-3 py-2 min-h-[44px] text-sm font-mono rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100"
            >
              LOGOUT
            </button>
          </div>
        </div>
      </div>

      <CountySelector value={selectedCounty} onChange={setSelectedCounty} />

      <div className="max-w-7xl mx-auto px-6 py-8">
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 mb-8">
          <div className="mb-6">
            <span className="text-xs font-mono text-gray-500 tracking-wider uppercase">TODAY'S ADVISORY</span>
            <h3 className={`font-mono text-4xl font-bold mt-2 ${actionColor}`}>{actionLabel}</h3>
          </div>
          <div className="flex flex-wrap gap-4 items-center">
            <DecisionBadge action={today.action} />
            {today.action === "IRRIGATE" && today.irrigate_amount > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-5 py-3">
                <small className="font-mono text-xs tracking-wider text-red-600 block mb-1">APPLY</small>
                <b className="font-mono text-2xl text-red-700">
                  {today.irrigate_amount.toFixed(1)}"
                </b>
                <span className="font-mono text-sm text-red-600 ml-2">INCHES TODAY</span>
              </div>
            )}
          </div>

          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <SimpleMetric label="Water used by crop" value={(today.depletion * 100).toFixed(0)} unit="%" />
            <SimpleMetric label="Refill point" value={(crop.mad * 100).toFixed(0)} unit="%" subtext="water below this = irrigate" />
            <SimpleMetric label="Crop water today" value={today.etc.toFixed(2)} unit="in" subtext="inches the crop drinks" />
            <SimpleMetric label="Rain next 7 days" value={today.rain_7d.toFixed(1)} unit="in" />
            <SimpleMetric label="Water to add" value={today.depletion >= crop.mad ? (0.9 * crop.aw - today.soil_water).toFixed(2) : "0.00"} unit="in" subtext="how much to irrigate" />
          </div>
        </section>

        <WeatherStrip forecast={forecast} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 space-y-6">
            <HistoryCard history={history} />

            <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h4 className="font-mono text-lg font-semibold text-gray-800 mb-4">SOIL MOISTURE</h4>
              <div className="flex flex-col md:flex-row items-center md:items-start gap-4">
                <SoilGauge pct={today.soil_pct} />
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="font-mono text-sm text-gray-600">Current soil water:</span>
                    <span className="font-mono text-sm font-semibold text-gray-800">{today.soil_water.toFixed(1)}" of {crop.aw.toFixed(1)}"</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-mono text-sm text-gray-600">Available water capacity:</span>
                    <span className="font-mono text-sm font-semibold text-gray-800">{crop.aw.toFixed(1)}"</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-mono text-sm text-gray-600">Depletion:</span>
                    <span className="font-mono text-sm font-semibold text-gray-800">{Math.round(today.depletion * 100)}%</span>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div className="space-y-6">
            <DroughtCard drought={drought} />

            <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h4 className="font-mono text-lg font-semibold text-gray-800 mb-4">PLANTING WINDOW</h4>
              {planting_window ? (
                <div className="space-y-3">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="font-mono text-xs text-gray-500 uppercase tracking-wider mb-1">FROST 50%</p>
                    <p className="font-mono text-lg font-bold text-gray-800">
                      {planting_window.frost_50pct}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="font-mono text-xs text-gray-500 uppercase tracking-wider mb-1">LATEST SAFE PLANT</p>
                    <p className="font-mono text-lg font-bold text-gray-800">
                      {planting_window.corn_start}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-sm">Planting window data not available</p>
              )}
            </section>

            <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h4 className="font-mono text-lg font-semibold text-gray-800 mb-4">RECENT ADVISORIES</h4>
              {outbox.length === 0 ? (
                <p className="text-gray-500 text-sm">No advisories sent yet.</p>
              ) : (
                <div className="space-y-2">
                  {outbox.slice(0, 3).map((o, i) => (
                    <div key={i} className="flex justify-between items-center border-b border-gray-200 pb-2 last:border-0">
                      <span className="font-mono text-xs tracking-wider text-gray-500">
                        {new Date(o.sent_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
                        })}
                      </span>
                      <span className="font-mono text-xs tracking-wider text-gray-500 max-w-xs truncate">{o.body}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
