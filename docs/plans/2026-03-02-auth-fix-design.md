# Auth Fix Design — Infinite Loader & Auto-Logout

**Дата:** 2026-03-02
**Статус:** Утверждён

---

## Проблема

### Баг 1 — Вечный лоадер при логине (HTTP 499)

`client.ts` в перехватчике ответов вызывает `window.location.href = '/login'` при провале refresh токена. Это полная перезагрузка страницы. Если она срабатывает пока login POST запрос ещё в полёте — браузер убивает запрос, nginx логирует 499, кнопка остаётся в `isLoading=true` навсегда.

Подтверждено в nginx логах: три подряд `POST /api/v1/auth/login HTTP/1.1" 499 0`.

### Баг 2 — Не разлогинивает при истечении токенов

`clearTokens()` очищает localStorage и in-memory токены, но не вызывает `useAuthStore.logout()`. Zustand `auth-storage` хранит `{ isAuthenticated: true }`. После `window.location.href` страница перезагружается, но Zustand rehydrates с устаревшим состоянием.

---

## Решение — Custom DOM Event (Вариант A)

HTTP-слой (`client.ts`) диспатчит кастомное DOM-событие. React-компонент `AuthWatcher` слушает его и выполняет навигацию через React Router + обновляет Zustand.

**Принцип:** HTTP-слой не знает о React Router. React-слой не знает о деталях HTTP.

---

## Изменяемые файлы

| Файл | Изменение |
|------|-----------|
| `shared/api/client.ts` | Заменить `window.location.href` на `dispatchEvent` |
| `features/protected-route/ui/AuthWatcher.tsx` | Новый компонент |
| `features/protected-route/index.ts` | Экспортировать `AuthWatcher` |
| `app/layouts/AdminLayout/AdminLayout.tsx` | Подключить `AuthWatcher` |
| `pages/login/ui/LoginPage.tsx` | Редирект если уже авторизован |

---

## Детали реализации

### `client.ts` — убрать `window.location.href`

```diff
  } catch (refreshError) {
    this.clearTokens();
-   window.location.href = '/login';
-   return Promise.reject(refreshError);
+   window.dispatchEvent(new CustomEvent('auth:unauthorized'));
+   return Promise.reject(refreshError);
  }
```

### `AuthWatcher.tsx` — новый компонент

```tsx
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@entities/auth';

export const AuthWatcher = () => {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    const handler = () => {
      logout();
      navigate('/login', { replace: true });
    };
    window.addEventListener('auth:unauthorized', handler);
    return () => window.removeEventListener('auth:unauthorized', handler);
  }, [navigate, logout]);

  return null;
};
```

### `AdminLayout.tsx` — монтировать `AuthWatcher`

```tsx
import { AuthWatcher } from '@features/protected-route';

export const AdminLayout = () => (
  <Flex direction="column" minH="100vh">
    <AuthWatcher />
    <AdminHeader />
    ...
  </Flex>
);
```

`AuthWatcher` монтируется в `AdminLayout` (а не в `App`), потому что `useNavigate` требует контекст React Router.

### `LoginPage.tsx` — редирект если авторизован

```tsx
import { Navigate } from 'react-router-dom';
import { authApi } from '@shared/api';
import { LoginForm } from '@features/auth-login';

export const LoginPage = () => {
  if (authApi.isAuthenticated()) {
    return <Navigate to="/admin" replace />;
  }
  return <LoginForm />;
};
```

---

## Flow после фикса

```
Токен протух → API запрос → 401
                    │
                    ▼
        interceptor: performRefresh()
                    │
            ┌───────┴───────┐
            │    success    │ → новый токен → запрос повторяется
            └───────────────┘
                    │
            ┌───────┴───────┐
            │     fail      │ → clearTokens()
            └───────────────┘
                    │
                    ▼
        dispatchEvent('auth:unauthorized')
                    │
                    ▼
        AuthWatcher (смонтирован в AdminLayout)
        ├── logout()  → Zustand: isAuthenticated = false
        └── navigate('/login', replace)  → без перезагрузки
                    │
                    ▼
        LoginPage → isAuthenticated() = false → показывает форму
        Пользователь логинится нормально
```

---

## Что не меняется

- `ProtectedRoute` — логика без изменений
- `store.ts` — метод `logout()` уже есть
- Все API endpoints — без изменений
- Никаких новых зависимостей
