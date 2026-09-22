export interface County {
  fips: string;
  name: string;
  state: string;
  lat: number;
  lon: number;
}

export interface SoilData {
  water_source?: "stored" | "assumed";
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
  advice_uncertain?: boolean;
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
  advice_uncertain?: boolean;
  soil_min_pct?: number;
  soil_max_pct?: number;
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