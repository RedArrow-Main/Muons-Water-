export interface County {
  fips: string;
  name: string;
  state: string;
  lat: number;
  lon: number;
}

export interface SoilData {
  type: string;
  awc: number;
}

export type GrowthStage = "vegetative" | "pollination" | "grain_fill" | "maturity";

export interface Crop {
  id: string;
  aw: number;
  mad: number;
  base_mad?: number;
  planting_date?: string | null;
  growth_stage?: GrowthStage;
  stage_label?: string;
  gdd_pct?: number;
  cumulative_gdd?: number;
  gdd_to_maturity?: number;
}

export interface CropCatalog {
  id: string;
  base_temp_f: number;
  gdd_total: number;
  root_depth_in: number;
  mad_fraction: number;
  kc_initial: number;
  kc_mid: number;
  kc_end: number;
}

export interface FarmCrop {
  crop_id: string;
  planting_date: string | null;
}

export interface Farm {
  id: number;
  county_fips: string;
  name: string;
  acres: number | null;
  created_at: string;
  crops: FarmCrop[];
}

export interface ForecastDay {
  date: string;
  tmax_f: number;
  tmin_f: number;
  precip_in: number;
  et0_in: number;
  gdd: number;
  etc: number;
  soil_water: number;
  depletion: number;
  action: "HOLD" | "SCHEDULE" | "IRRIGATE";
}

export interface TodayData {
  gdd: number;
  etc: number;
  soil_water: number;
  soil_pct: number;
  depletion: number;
  action: "HOLD" | "SCHEDULE" | "IRRIGATE";
  irrigate_amount: number;
  rain_today: number;
  rain_7d: number;
}

export interface HistoryData {
  july_avg_high: number;
  july_avg_low: number;
  july_total_rain: number;
  last_7d_rain: number;
  last_7d_et: number;
}

export interface PlantingWindow {
  frost_50pct: string;
  corn_start: string;
  corn_end: string;
}

export interface AdvisoryResponse {
  county: County;
  soil: SoilData;
  crop: Crop;
  forecast: ForecastDay[];
  today: TodayData;
  history: HistoryData;
  drought: { level: "D1" | "D2" | "D3" | "D4" } | null;
  outbox: Array<{ sent_at: string; body: string }>;
  planting_window: PlantingWindow;
  data_as_of: {
    last_pipeline_at: string | null;
    last_pipeline_status: string | null;
    last_pipeline_rows: number;
  };
}

export async function getAdvisory(
  fips: string,
  opts: { cropId?: string; plantingDate?: string; signal?: AbortSignal } = {}
): Promise<AdvisoryResponse | null> {
  try {
    const params = new URLSearchParams();
    if (opts.cropId) params.set("crop_id", opts.cropId);
    if (opts.plantingDate) params.set("planting_date", opts.plantingDate);
    const qs = params.toString();
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const url = `${baseUrl}/api/advisory/${fips}${qs ? `?${qs}` : ""}`;
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
      credentials: "include",
      signal: opts.signal,
    });
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        throw new Error("UNAUTHENTICATED");
      }
      return null;
    }
    return response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    console.error("Failed to fetch advisory:", error);
    return null;
  }
}

export async function getCrops(): Promise<CropCatalog[]> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${baseUrl}/api/crops`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      return [];
    }
    return response.json();
  } catch (error) {
    console.error("Failed to fetch crops:", error);
    return [];
  }
}

export async function getFarms(): Promise<Farm[]> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${baseUrl}/api/farm`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      return [];
    }
    return response.json();
  } catch (error) {
    console.error("Failed to fetch farms:", error);
    return [];
  }
}

export async function getCounties(): Promise<County[]> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${baseUrl}/api/counties`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      return [];
    }
    return response.json();
  } catch (error) {
    console.error("Failed to fetch counties:", error);
    return [];
  }
}

export async function login(email: string, password: string): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${baseUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let msg = "Login failed";
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
}

export async function register(email: string, password: string): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${baseUrl}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let msg = "Registration failed";
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
}

export async function logout(): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  await fetch(`${baseUrl}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}
