import { useCallback, useEffect, useState } from 'react';

const FAVORITES_KEY = 'fp.favorites.v1';
const SCOPE_KEY = 'fp.scope.v1';

export type Scope = 'favorites' | 'all';

function readFavorites(): string[] {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((t) => typeof t === 'string') : [];
  } catch {
    return [];
  }
}

/** Избранные фьючерсы: хранятся в localStorage браузера.
 *  Если понадобится синхронизация между устройствами — заменяется
 *  на хранение в бэкенде без изменения вызывающего кода. */
export function useFavorites() {
  const [favorites, setFavorites] = useState<string[]>(readFavorites);

  useEffect(() => {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
  }, [favorites]);

  useEffect(() => {
    // Синхронизация между вкладками браузера
    const onStorage = (event: StorageEvent) => {
      if (event.key === FAVORITES_KEY) setFavorites(readFavorites());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const toggle = useCallback((ticker: string) => {
    setFavorites((prev) =>
      prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker],
    );
  }, []);

  const isFavorite = useCallback((ticker: string) => favorites.includes(ticker), [favorites]);

  return { favorites, isFavorite, toggle };
}

export function readScope(favoritesCount: number): Scope {
  const saved = localStorage.getItem(SCOPE_KEY);
  if (saved === 'favorites' || saved === 'all') return saved;
  return favoritesCount > 0 ? 'favorites' : 'all';
}

export function writeScope(scope: Scope) {
  localStorage.setItem(SCOPE_KEY, scope);
}
