import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fmtInt, useApi } from '../api/client';
import { useFavorites } from '../api/useFavorites';
import type { HistoryResponse } from '../api/types';
import { HistoryCharts, PERIOD_OPTIONS } from '../components/HistoryCharts';
import { DataSourceBadge, ErrorBox, Spinner } from '../components/common';

export function InstrumentPage() {
  const { ticker = '' } = useParams();
  const [days, setDays] = useState(90);
  const { isFavorite, toggle } = useFavorites();
  const history = useApi<HistoryResponse>('/positions/history', { ticker, days });
  const fav = isFavorite(ticker);

  const data = history.data;

  return (
    <div className="page">
      <div className="page-head">
        <h1>
          <Link to="/" className="crumb">← Все инструменты</Link> {ticker}
          <button
            className={`star-btn head-star${fav ? ' active' : ''}`}
            title={fav ? 'Убрать из избранного' : 'Добавить в избранное'}
            aria-label={fav ? `Убрать ${ticker} из избранного` : `Добавить ${ticker} в избранное`}
            onClick={() => toggle(ticker)}
          >
            {fav ? '★' : '☆'}
          </button>
        </h1>
        <DataSourceBadge source={data?.source} />
      </div>
      <p className="subtitle">{data?.name ?? 'История открытых позиций по категориям участников'}</p>

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

      {history.loading && !data ? (
        <Spinner
          label={
            days > 90
              ? 'Первый запрос длинного периода может занять до минуты: докачиваем историю с биржи…'
              : 'Загрузка данных…'
          }
        />
      ) : history.error ? (
        <ErrorBox message={history.error} onRetry={history.reload} />
      ) : data ? (
        <>
          <HistoryCharts
            points={data.points}
            prices={data.prices}
            priceLabel={data.price_label ?? undefined}
          />

          <section className="chart-box">
            <h2>Итоги за период: открыто и закрыто позиций, шт.</h2>
            <table className="agg-table">
              <thead>
                <tr>
                  <th>Категория</th>
                  <th>Лонг открыт</th>
                  <th>Лонг закрыт</th>
                  <th>Шорт открыт</th>
                  <th>Шорт закрыт</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="group-fiz">Физические лица</td>
                  <td className="num">{fmtInt.format(data.aggregates.fiz_long_opened)}</td>
                  <td className="num">{fmtInt.format(data.aggregates.fiz_long_closed)}</td>
                  <td className="num">{fmtInt.format(data.aggregates.fiz_short_opened)}</td>
                  <td className="num">{fmtInt.format(data.aggregates.fiz_short_closed)}</td>
                </tr>
                <tr>
                  <td className="group-jur">Юридические лица</td>
                  <td className="num">{fmtInt.format(data.aggregates.jur_long_opened)}</td>
                  <td className="num">{fmtInt.format(data.aggregates.jur_long_closed)}</td>
                  <td className="num">{fmtInt.format(data.aggregates.jur_short_opened)}</td>
                  <td className="num">{fmtInt.format(data.aggregates.jur_short_closed)}</td>
                </tr>
              </tbody>
            </table>
            <p className="note">
              «Открыто/закрыто» — сумма дневных приростов/снижений числа контрактов за {data.aggregates.days} торговых дней.
              В последний день истории позиций может быть ноль, если это первая точка периода.
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
