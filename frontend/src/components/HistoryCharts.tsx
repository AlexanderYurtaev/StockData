import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fmtDate, fmtInt } from '../api/client';
import type { HistoryPoint, PricePoint } from '../api/types';

/** Периоды, доступные в селекторах истории (дней; год и больше — длинные). */
export const PERIOD_OPTIONS = [
  { days: 14, label: '14 дней' },
  { days: 30, label: '30 дней' },
  { days: 60, label: '60 дней' },
  { days: 90, label: '90 дней' },
  { days: 365, label: '1 год' },
  { days: 1095, label: '3 года' },
  { days: 1825, label: '5 лет' },
];

interface LegendEntry {
  value?: string;
  dataKey?: string | number;
  color?: string;
  payload?: { dataKey?: string | number; strokeDasharray?: string | number };
}

/** Легенда с кликабельными сериями: клик по категории скрывает/показывает линию. */
function ClickableLegend({
  payload,
  hidden,
  onToggle,
}: {
  payload?: LegendEntry[];
  hidden: Record<string, boolean>;
  onToggle: (key: string) => void;
}) {
  if (!payload) return null;
  return (
    <ul className="legend-list">
      {payload.map((item) => {
        const key = String(item.payload?.dataKey ?? item.dataKey ?? item.value ?? '');
        const dashed = Boolean(item.payload?.strokeDasharray);
        return (
          <li key={key}>
            <button
              type="button"
              className={`legend-item${hidden[key] ? ' dimmed' : ''}`}
              aria-pressed={!hidden[key]}
              title={hidden[key] ? 'Показать линию' : 'Скрыть линию'}
              onClick={() => onToggle(key)}
            >
              <span
                className="legend-swatch"
                style={dashed
                  ? { background: `repeating-linear-gradient(90deg, ${item.color} 0 5px, transparent 5px 9px)` }
                  : { background: item.color }}
              />
              {item.value}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

const ABS_SERIES = [
  { key: 'fiz_long', title: 'Физлица — лонг', color: '#1a9e55', dashed: false },
  { key: 'fiz_short', title: 'Физлица — шорт', color: '#7fd0a4', dashed: true },
  { key: 'jur_long', title: 'Юрлица — лонг', color: '#e07b00', dashed: false },
  { key: 'jur_short', title: 'Юрлица — шорт', color: '#9a6fd8', dashed: true },
] as const;

/** Пара графиков истории: чистые позиции (сверху, с линией цены базового
 *  актива на правой оси) и все четыре серии (снизу).
 *  `uniform` — данные идут с переменным шагом (сэмплированные агрегаты):
 *  длинные периоды сворачиваем в недельные/месячные точки, чтобы ось
 *  оставалась равномерной. */
export function HistoryCharts({
  points,
  prices,
  priceLabel,
  uniform = false,
}: {
  points: HistoryPoint[];
  prices?: PricePoint[];
  priceLabel?: string | null;
  uniform?: boolean;
}) {
  // По умолчанию показываем только физлиц; юрлица и цена включаются в легенде
  const [hiddenNet, setHiddenNet] = useState<Record<string, boolean>>({ jur_net: true, price: true });
  const [hiddenAbs, setHiddenAbs] = useState<Record<string, boolean>>({ jur_long: true, jur_short: true });
  const priceName = priceLabel ?? 'Цена';

  const rows = useMemo(() => {
    const priceByDate = new Map((prices ?? []).map((p) => [p.date, p.close]));
    return points.map((point) => {
      const [y, m, d] = point.date.split('-').map(Number);
      const t = new Date(y, m - 1, d).getTime();
      return {
        t,
        price: priceByDate.get(point.date),
        fiz_long: point.fiz_long,
        fiz_short: point.fiz_short,
        jur_long: point.jur_long,
        jur_short: point.jur_short,
        fiz_net: point.fiz_long - point.fiz_short,
        jur_net: point.jur_long - point.jur_short,
      };
    });
  }, [points, prices]);

  const spanDays = rows.length > 1 ? (rows[rows.length - 1].t - rows[0].t) / 86400000 : 0;
  const display = useMemo(() => {
    let list = rows;
    if (uniform && spanDays > 110) {
      // Сэмплированные агрегаты: длинные периоды сворачиваем в недельные
      // (до года) или месячные (дольше) точки — ось остаётся равномерной
      const bucketMs = spanDays > 400 ? 30 * 86400000 : 7 * 86400000;
      const byBucket = new Map<number, (typeof rows)[number]>();
      for (const row of rows) byBucket.set(Math.floor(row.t / bucketMs), row);
      list = [...byBucket.values()];
    }
    const monthly = uniform && spanDays > 400;
    const fmt = monthly
      ? new Intl.DateTimeFormat('ru-RU', { month: 'short', year: 'numeric' })
      : undefined;
    return list.map((row) => {
      const d = new Date(row.t);
      const dd = String(d.getDate()).padStart(2, '0');
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const label = fmt
        ? fmt.format(d).replace(' г.', '')
        : spanDays > 110
          ? `${dd}.${mm}.${String(d.getFullYear()).slice(2)}`
          : `${dd}.${mm}`;
      return { ...row, label };
    });
  }, [rows, uniform, spanDays]);

  if (!points.length) return null;
  const range = `${fmtDate(points[0].date)} — ${fmtDate(points[points.length - 1].date)}`;
  const formatFull = (t: number) => {
    const d = new Date(t);
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${dd}.${mm}.${d.getFullYear()}`;
  };
  const fmtPrice = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });
  const hasPrice = (prices?.length ?? 0) > 0;
  const tooltipValue = (value: unknown, name: unknown) =>
    String(name) === priceName ? fmtPrice.format(Number(value)) : fmtInt.format(Number(value));

  return (
    <>
      <section className="chart-box">
        <h2>Чистые позиции, контрактов (лонг − шорт) ({range})</h2>
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={display} margin={{ top: 8, right: hasPrice ? 8 : 24, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e7ee" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} minTickGap={24} />
            <YAxis yAxisId="pos" tick={{ fontSize: 12 }} tickFormatter={(v: number) => fmtInt.format(v)} width={90} />
            {hasPrice && (
              <YAxis
                yAxisId="price"
                orientation="right"
                tick={{ fontSize: 12 }}
                tickFormatter={(v: number) => fmtPrice.format(v)}
                width={76}
                domain={['auto', 'auto']}
              />
            )}
            <Tooltip formatter={tooltipValue} labelFormatter={(label, payload) =>
              payload?.length ? formatFull((payload[0].payload as { t: number }).t) : String(label)
            } />
            <ReferenceLine yAxisId="pos" y={0} stroke="#8a93a3" strokeWidth={1.5} />
            <Legend content={<ClickableLegend hidden={hiddenNet} onToggle={(key) => setHiddenNet((prev) => ({ ...prev, [key]: !prev[key] }))} />} />
            <Line yAxisId="pos" type="monotone" dataKey="fiz_net" name="Физлица — чистые" stroke="#1a9e55" strokeWidth={2.5} dot={false} hide={!!hiddenNet.fiz_net} />
            <Line yAxisId="pos" type="monotone" dataKey="jur_net" name="Юрлица — чистые" stroke="#e07b00" strokeWidth={2.5} dot={false} hide={!!hiddenNet.jur_net} />
            {hasPrice && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="price"
                name={priceName}
                stroke="#0f5fd7"
                strokeWidth={2}
                dot={false}
                connectNulls
                hide={!!hiddenNet.price}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
        <p className="note">
          Чистая позиция = длинные позиции минус короткие. Значения выше нуля — категория
          в нетто-лонге, ниже нуля — в нетто-шорте. Нажмите на категорию в легенде, чтобы
          скрыть или показать линию.
          {hasPrice && ' Линия цены построена по правой оси (закрытие базового актива).'}
        </p>
      </section>

      <section className="chart-box">
        <h2>Открытые позиции, контрактов ({range})</h2>
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={display} margin={{ top: 8, right: 24, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e7ee" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} minTickGap={24} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => fmtInt.format(v)} width={90} />
            <Tooltip
              formatter={tooltipValue}
              labelFormatter={(label, payload) =>
                payload?.length ? formatFull((payload[0].payload as { t: number }).t) : String(label)
              }
            />
            <Legend content={<ClickableLegend hidden={hiddenAbs} onToggle={(key) => setHiddenAbs((prev) => ({ ...prev, [key]: !prev[key] }))} />} />
            {ABS_SERIES.map((series) => (
              <Line
                key={series.key}
                type="monotone"
                dataKey={series.key}
                name={series.title}
                stroke={series.color}
                strokeWidth={2}
                strokeDasharray={series.dashed ? '6 4' : undefined}
                dot={false}
                hide={!!hiddenAbs[series.key]}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <p className="note">Нажмите на категорию в легенде, чтобы скрыть или показать линию.</p>
      </section>
    </>
  );
}
