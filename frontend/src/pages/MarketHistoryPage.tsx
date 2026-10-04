import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../api/client';
import type { TotalsHistoryResponse } from '../api/types';
import { HistoryCharts, PERIOD_OPTIONS } from '../components/HistoryCharts';
import { DataSourceBadge, ErrorBox, Spinner } from '../components/common';

export function MarketHistoryPage() {
  const [days, setDays] = useState(90);
  const totals = useApi<TotalsHistoryResponse>('/positions/totals-history', { days });
  const data = totals.data;

  return (
    <div className="page">
      <div className="page-head">
        <h1><Link to="/" className="crumb">← К позициям</Link> Динамика по рынку</h1>
        <DataSourceBadge source={data?.source} />
      </div>
      <p className="subtitle">
        Суммарные позиции физических и юридических лиц по всем {data?.instruments ?? '…'} фьючерсам
        списка (акции и фондовые индексы) — те же агрегаты, что в карточках на главной странице.
      </p>

      <div className="toolbar">
        <label className="days-picker">
          Период:
          <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
            {PERIOD_OPTIONS.map((option) => (
              <option key={option.days} value={option.days}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      {totals.loading && !data ? (
        <Spinner label="Первый запрос периода может занять до минуты: докачиваем историю с биржи…" />
      ) : totals.error ? (
        <ErrorBox message={totals.error} onRetry={totals.reload} />
      ) : data ? (
        <HistoryCharts points={data.points} prices={data.prices} priceLabel={data.price_label} uniform />
      ) : null}
    </div>
  );
}
