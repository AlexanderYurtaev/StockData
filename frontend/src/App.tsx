import { NavLink, Route, Routes } from 'react-router-dom';
import { AboutPage } from './pages/AboutPage';
import { InstrumentPage } from './pages/InstrumentPage';
import { MarketHistoryPage } from './pages/MarketHistoryPage';
import { PositionsPage } from './pages/PositionsPage';

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="brand-mark">ФЮ</span>
          <span className="brand-name">Позиции по фьючерсам на акции и индексы</span>
        </NavLink>
        <nav className="nav">
          <NavLink to="/" end>Позиции</NavLink>
          <NavLink to="/market">Динамика рынка</NavLink>
          <NavLink to="/about">О проекте</NavLink>
          <a href="/docs" target="_blank" rel="noreferrer">API</a>
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<PositionsPage />} />
          <Route path="/market" element={<MarketHistoryPage />} />
          <Route path="/instrument/:ticker" element={<InstrumentPage />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </main>
      <footer className="footer">
        Данные: Московская биржа, отчёт «Открытые позиции». Публикация с лагом ~1 торговый день.
        Не является инвестиционной рекомендацией.
      </footer>
    </div>
  );
}
