import type { DataSourceInfo } from '../api/types';

export function DataSourceBadge({ source }: { source: DataSourceInfo | undefined }) {
  if (!source) return null;
  return (
    <span className={`source-badge ${source.real ? 'source-real' : 'source-demo'}`} title={source.label}>
      <span className="source-dot" />
      {source.label}
    </span>
  );
}

export function ChangeBadge({ value, suffix = '' }: { value: number; suffix?: string }) {
  if (value === 0) return <span className="change change-zero">0</span>;
  const arrow = value > 0 ? '▲' : '▼';
  return (
    <span className={`change ${value > 0 ? 'change-up' : 'change-down'}`}>
      {arrow} {new Intl.NumberFormat('ru-RU').format(Math.abs(value))}
      {suffix}
    </span>
  );
}

export function Spinner({ label = 'Загрузка данных…' }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-box">
      <strong>Не удалось загрузить данные</strong>
      <p>{message}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}

/** Иконка «ⓘ» со всплывающей подсказкой: видна при наведении и по клику. */
export function Info({ text, align = 'left' }: { text: string; align?: 'left' | 'right' }) {
  return (
    <span
      className={`info${align === 'right' ? ' info-right' : ''}`}
      tabIndex={0}
      role="note"
      aria-label={text}
      onClick={(event) => event.stopPropagation()}
    >
      <span className="info-icon" aria-hidden="true">i</span>
      <span className="info-tooltip">{text}</span>
    </span>
  );
}
