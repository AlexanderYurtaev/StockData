import { Link } from 'react-router-dom';
import { fmtDate, fmtInt } from '../api/client';
import type { SummaryResponse } from '../api/types';
import { Info } from './common';

const CATEGORY_HINT =
  'Суммарные открытые позиции категории по всем фьючерсам списка, на дату из карточки ' +
  '«Рынок в целом». Лонг — купленные контракты, шорт — проданные. Нетто = лонг − шорт. ' +
  'Доля — процент категории в совокупном объёме (лонг + шорт) всех инструментов.';

const HOLDERS_HINT =
  'Количество лиц с открытыми позициями, просуммированное по инструментам. ' +
  'Не равно числу уникальных лиц: один человек может торговать несколькими фьючерсами.';

export function SummaryCards({ summary }: { summary: SummaryResponse }) {
  return (
    <section className="summary" aria-label="Сводка по рынку">
      {summary.items.map((item) => (
        <Link key={item.category} to="/market" className="card-link" title="Открыть график динамики">
          <article className={`summary-card ${item.category}`}>
            <header>
              <h3>
                {item.title}
                <Info text={CATEGORY_HINT} />
              </h3>
              <span className="share">доля {item.share_pct}%</span>
            </header>
            <div className="summary-grid">
              <div className="cell">
                <span className="label">Лонг</span>
                <span className="value value-long">{fmtInt.format(item.long)}</span>
              </div>
              <div className="cell">
                <span className="label">Шорт</span>
                <span className="value value-short">{fmtInt.format(item.short)}</span>
              </div>
              <div className="cell">
                <span className="label">Нетто</span>
                <span className={`value ${item.net >= 0 ? 'value-long' : 'value-short'}`}>
                  {item.net > 0 ? '+' : ''}
                  {fmtInt.format(item.net)}
                </span>
              </div>
            </div>
            <footer>
              лиц с открытыми позициями: {fmtInt.format(item.long_holders)} (лонг) / {fmtInt.format(item.short_holders)} (шорт)
              <Info text={HOLDERS_HINT} />
            </footer>
          </article>
        </Link>
      ))}
      <article className="summary-card market">
        <header>
          <h3>
            Рынок в целом
            <Info
              text={`Совокупный объём открытых позиций (лонг + шорт) по всем ${summary.instruments} ` +
                'фьючерсам списка. Суммарный лонг всегда равен суммарному шорту: у каждого ' +
                'контракта есть покупатель и продавец.'}
            />
          </h3>
          <span className="share">на {fmtDate(summary.date)}</span>
        </header>
        <div className="summary-grid">
          <div className="cell">
            <span className="label">Всего открытых позиций</span>
            <span className="value">{fmtInt.format(summary.total)}</span>
          </div>
          <div className="cell">
            <span className="label">Изменение за день</span>
            <span className="value">{summary.total_change > 0 ? '+' : ''}{fmtInt.format(summary.total_change)}</span>
          </div>
        </div>
        <footer>в сумму входят только фьючерсы из таблицы ниже — акции и фондовые индексы</footer>
      </article>
    </section>
  );
}
