import { DataSourceBadge } from '../components/common';

export function AboutPage() {
  return (
    <div className="page narrow">
      <div className="page-head">
        <h1>О проекте</h1>
      </div>
      <p>
        Сервис показывает открытые и закрытые позиции физических и юридических лиц
        по фьючерсам на акции и ведущим фондовым индексам (МосБиржи, РТС) на срочном
        рынке Московской биржи, а также цену базового актива для сопоставления.
        Позиции приходят из отчёта биржи «Открытые позиции» (лаг около одного
        торгового дня), цены — из открытого API ISS Московской биржи.
      </p>
      <h2>Архитектура</h2>
      <ul>
        <li><strong>Бэкенд</strong> — FastAPI, слои: API (версионируется, <code>/api/v1</code>) → сервисы (преобразования данных) → провайдеры (источники данных с фолбэком и кэшем).</li>
        <li><strong>Источники данных</strong> — подключаются через единый интерфейс <code>DataProvider</code>. Сейчас: отчёт MOEX «Открытые позиции» (реальные данные) и детерминированный демо-генератор (офлайн-фолбэк).</li>
        <li><strong>Фронтенд</strong> — React + TypeScript (Vite), страницы на роутере, типизированный клиент API.</li>
      </ul>
      <h2>Точки расширения</h2>
      <ul>
        <li>Новый источник данных — реализовать <code>DataProvider</code> и добавить его в цепочку <code>DataService</code>.</li>
        <li>Новая страница/виджет — добавить роут и переиспользовать хук <code>useApi</code>.</li>
        <li>Новые срезы (опционы, индексные фьючерсы) — расширить параметр <code>market</code> провайдера и фильтры API.</li>
      </ul>
      <h2>API</h2>
      <ul className="api-list">
        <li><code>GET /api/v1/positions?view=open|closed</code> — таблица позиций</li>
        <li><code>GET /api/v1/positions/summary</code> — сводка по категориям</li>
        <li><code>GET /api/v1/positions/history?ticker=GAZR&days=30</code> — история инструмента</li>
        <li><code>GET /api/v1/instruments</code> — список фьючерсов на акции</li>
        <li><code>GET /api/v1/system/health</code> — состояние провайдеров</li>
        <li>Интерактивная документация: <a href="/docs" target="_blank" rel="noreferrer">Swagger UI</a></li>
      </ul>
      <p className="note">Источник данных: <DataSourceBadge source={{ provider: 'moex', real: true, label: 'MOEX — отчёт «Открытые позиции» (web.moex.com)' }} /></p>
    </div>
  );
}
