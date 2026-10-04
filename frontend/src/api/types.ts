/** Типы, зеркалящие схемы бэкенда (app/schemas). */

export interface DataSourceInfo {
  provider: string;
  real: boolean;
  label: string;
}

export interface CategoryStat {
  long: number;
  short: number;
  long_change: number;
  short_change: number;
  long_holders: number;
  short_holders: number;
}

export interface OpenPositionRow {
  ticker: string;
  name: string;
  kind: 'standard' | 'mini' | 'daily';
  date: string;
  fiz: CategoryStat;
  jur: CategoryStat;
  total: number;
  total_change: number;
}

export interface ClosedPositionRow {
  ticker: string;
  name: string;
  kind: 'standard' | 'mini' | 'daily';
  date: string;
  fiz_long_closed: number;
  fiz_short_closed: number;
  fiz_long_opened: number;
  fiz_short_opened: number;
  jur_long_closed: number;
  jur_short_closed: number;
  jur_long_opened: number;
  jur_short_opened: number;
  net_change_fiz: number;
  net_change_jur: number;
}

export type PositionsRow = OpenPositionRow | ClosedPositionRow;

export interface PositionsResponse {
  items: PositionsRow[];
  total: number;
  date: string | null;
  view: 'open' | 'closed';
  source: DataSourceInfo;
}

export interface SummaryCategory {
  category: 'individual' | 'legal_entity';
  title: string;
  long: number;
  short: number;
  net: number;
  share_pct: number;
  long_holders: number;
  short_holders: number;
}

export interface SummaryResponse {
  date: string;
  items: SummaryCategory[];
  total: number;
  total_change: number;
  instruments: number;
  source: DataSourceInfo;
}

export interface HistoryPoint {
  date: string;
  fiz_long: number;
  fiz_short: number;
  jur_long: number;
  jur_short: number;
  total: number;
}

export interface HistoryAggregates {
  days: number;
  fiz_long_opened: number;
  fiz_long_closed: number;
  fiz_short_opened: number;
  fiz_short_closed: number;
  jur_long_opened: number;
  jur_long_closed: number;
  jur_short_opened: number;
  jur_short_closed: number;
}

export interface PricePoint {
  date: string;
  close: number;
}

export interface HistoryResponse {
  ticker: string;
  name: string;
  points: HistoryPoint[];
  aggregates: HistoryAggregates;
  prices: PricePoint[];
  price_label: string | null;
  source: DataSourceInfo;
}

export interface TotalsHistoryResponse {
  points: HistoryPoint[];
  instruments: number;
  prices: PricePoint[];
  price_label: string | null;
  source: DataSourceInfo;
}

export interface Instrument {
  ticker: string;
  name: string;
  kind: 'standard' | 'mini' | 'daily';
}

export interface InstrumentListResponse {
  items: Instrument[];
  total: number;
  source: DataSourceInfo;
}
