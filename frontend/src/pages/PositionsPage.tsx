import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fmtDate, fmtInt, useApi } from '../api/client';
import { readScope, useFavorites, writeScope } from '../api/useFavorites';
import type { Scope } from '../api/useFavorites';
import type { OpenPositionRow, PositionsResponse, SummaryResponse } from '../api/types';
import { ChangeBadge, DataSourceBadge, ErrorBox, Info, Spinner } from '../components/common';
import { SummaryCards } from '../components/SummaryCards';

const PAGE_SIZE = 25;

const COLUMNS: { key: string; title: string; group: 'fiz' | 'jur' | 'total' | '' }[] = [
  { key: 'ticker', title: 'Инструмент', group: '' },
  { key: 'fiz_long', title: 'Лонг', group: 'fiz' },
  { key: 'fiz_short', title: 'Шорт', group: 'fiz' },
  { key: 'jur_long', title: 'Лонг', group: 'jur' },
  { key: 'jur_short', title: 'Шорт', group: 'jur' },
  { key: 'total', title: 'Всего позиций', group: 'total' },
];

export function PositionsPage() {
  const { favorites, isFavorite, toggle } = useFavorites();
  const [scope, setScopeState] = useState<Scope>(() => readScope(favorites.length));
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [sort, setSort] = useState('');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);

  const setScope = (next: Scope) => {
    setScopeState(next);
    writeScope(next);
    setPage(0);
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const positions = useApi<PositionsResponse>('/positions', {
    query: debounced,
    sort,
    order,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    tickers: scope === 'favorites' && favorites.length > 0 ? favorites.join(',') : undefined,
  });
  const summary = useApi<SummaryResponse>('/positions/summary');

  const items = (positions.data?.items ?? []) as OpenPositionRow[];
  const total = positions.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggleSort = (key: string) => {
    if (sort === key) {
      setOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSort(key);
      setOrder('desc');
    }
    setPage(0);
  };

  const cellValue = (row: OpenPositionRow, key: string) => {
    if (key === 'ticker') {
      const fav = isFavorite(row.ticker);
      return (
        <div className="ticker-cell">
          <button
            className={`star-btn${fav ? ' active' : ''}`}
            title={fav ? 'Убрать из избранного' : 'Добавить в избранное'}
            aria-label={fav ? `Убрать ${row.ticker} из избранного` : `Добавить ${row.ticker} в избранное`}
            onClick={() => toggle(row.ticker)}
          >
            {fav ? '★' : '☆'}
          </button>
          <div className="ticker-names">
            <Link className="ticker" to={`/instrument/${row.ticker}`}>{row.ticker}</Link>
            <span className="row-name" title={row.name}>{row.name}</span>
          </div>
        </div>
      );
    }
    if (key === 'total') return fmtInt.format(row.total);
    const [category, side] = key.startsWith('fiz_') ? ['fiz', key.slice(4)] : ['jur', key.slice(4)];
    const stat = row[category as 'fiz' | 'jur'];
    const value = side === 'long' ? stat.long : stat.short;
    const change = side === 'long' ? stat.long_change : stat.short_change;
    return (
      <div className="stat-cell">
        <span className="stat-value">{fmtInt.format(value)}</span>
        <ChangeBadge value={change} />
      </div>
    );
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Позиции по фьючерсам на акции и индексы</h1>
        <DataSourceBadge source={positions.data?.source ?? summary.data?.source} />
      </div>

      {summary.data && <SummaryCards summary={summary.data} />}

      <div className="toolbar">
        <div className="segmented" role="tablist" aria-label="Состав списка">
          <button
            role="tab"
            aria-selected={scope === 'favorites'}
            className={scope === 'favorites' ? 'active' : ''}
            onClick={() => setScope('favorites')}
          >
            ★ Избранное{favorites.length > 0 ? ` (${favorites.length})` : ''}
          </button>
          <button
            role="tab"
            aria-selected={scope === 'all'}
            className={scope === 'all' ? 'active' : ''}
            onClick={() => setScope('all')}
          >
            Все инструменты
          </button>
        </div>
        <input
          className="search"
          type="search"
          placeholder="Поиск по тикеру или названию…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      {scope === 'favorites' && favorites.length === 0 ? (
        <div className="empty-favorites">
          <p>
            <strong>В избранном пока пусто.</strong><br />
            Отмечайте фьючерсы звёздочкой ★ в таблице — при открытии сайта
            по умолчанию будут показываться только они.
          </p>
          <button className="btn" onClick={() => setScope('all')}>Показать все инструменты</button>
        </div>
      ) : positions.loading && !positions.data ? (
        <Spinner />
      ) : positions.error ? (
        <ErrorBox message={positions.error} onRetry={positions.reload} />
      ) : (
        <>
          <div className="table-meta">
            {positions.data?.date && (
              <span>
                Данные на {fmtDate(positions.data.date)}
                <Info text="Отчёт биржи публикуется с лагом около одного торгового дня; сервис показывает последний опубликованный день. Выходные и праздники пропускаются." />
              </span>
            )}
            <span>
              Показаны {items.length} из {fmtInt.format(total)} инструментов
            </span>
          </div>
          <div className="table-wrap">
            <table className="positions-table">
              <thead>
                <tr>
                  <th rowSpan={2} className="sortable" onClick={() => toggleSort('ticker')}>Инструмент</th>
                  <th colSpan={2} className="group-fiz">
                    Физические лица
                    <Info text="Открытые позиции по инструменту, шт. Под значением — изменение к предыдущему торговому дню: ▲ рост, ▼ снижение." />
                  </th>
                  <th colSpan={2} className="group-jur">
                    Юридические лица
                    <Info text="Открытые позиции по инструменту, шт. Под значением — изменение к предыдущему торговому дню: ▲ рост, ▼ снижение." />
                  </th>
                  <th rowSpan={2} className="sortable" onClick={() => toggleSort('total')}>
                    Всего позиций
                    <Info text="Сумма лонга и шорта по четырём категориям инструмента (физлица и юрлица, лонг и шорт)." align="right" />
                  </th>
                </tr>
                <tr>
                  {COLUMNS.slice(1, 5).map((col) => (
                    <th key={col.key} className={`sortable sub ${col.group}`} onClick={() => toggleSort(col.key)}>
                      {col.title}
                      {sort === col.key && <span className="sort-arrow">{order === 'asc' ? ' ↑' : ' ↓'}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.ticker}>
                    {COLUMNS.map((col) => (
                      <td key={col.key} className={col.group ? `num ${col.group}` : ''}>
                        {cellValue(row, col.key)}
                      </td>
                    ))}
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={COLUMNS.length} className="empty">Ничего не найдено</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button className="btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              ← Назад
            </button>
            <span>
              Страница {page + 1} из {pages}
            </span>
            <button className="btn" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
              Вперёд →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
