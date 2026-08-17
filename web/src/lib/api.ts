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

export interface Crop {
  id: string;
  aw: number;
  mad: number;
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
  signal?: AbortSignal
): Promise<AdvisoryResponse | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${baseUrl}/api/advisory/${fips}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
      credentials: "include",
      signal,
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
