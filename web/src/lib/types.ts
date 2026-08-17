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
  july_avg_high: number | null;
  july_avg_low: number | null;
  july_total_rain: number | null;
  last_7d_rain: number | null;
  last_7d_et: number | null;
}

export interface PlantingWindow {
  frost_50pct: string;
  corn_start: string;
  corn_end: string;
}

export interface PipelineInfo {
  last_pipeline_at: string | null;
  last_pipeline_status: string | null;
  last_pipeline_rows: number;
}

export interface AdvisoryResponse {
  county: County;
  soil: SoilData;
  crop: Crop;
  forecast: ForecastDay[];
  today: TodayData;
  history: HistoryData;
  drought: { level: "NONE" | "D1" | "D2" | "D3" | "D4" } | null;
  outbox: Array<{ sent_at: string; body: string }>;
  planting_window: PlantingWindow;
  data_as_of: PipelineInfo;
}