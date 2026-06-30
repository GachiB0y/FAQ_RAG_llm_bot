# Auth Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Убрать вечный лоадер при логине и добавить корректный авто-разлогин при истечении токенов.

**Architecture:** Заменяем `window.location.href = '/login'` (полная перезагрузка) на Custom DOM Event `auth:unauthorized`. Новый компонент `AuthWatcher` слушает событие и выполняет навигацию через React Router + обновляет Zustand store. `LoginPage` получает редирект если токен уже валиден.

**Tech Stack:** React, React Router v7, Zustand, Axios interceptors, Custom DOM Events

---

### Task 1: Заменить `window.location.href` на `dispatchEvent` в `client.ts`

**Files:**
- Modify: `frontend/src/shared/api/client.ts:44-48`

**Step 1: Прочитать текущий код**

Открыть `frontend/src/shared/api/client.ts` и найти блок `catch (refreshError)` в interceptor:

```typescript
} catch (refreshError) {
  this.clearTokens();
  window.location.href = '/login';
  return Promise.reject(refreshError);
}
```

**Step 2: Заменить `window.location.href` на event**

Итоговый блок должен выглядеть так:

```typescript
} catch (refreshError) {
  this.clearTokens();
  window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  return Promise.reject(refreshError);
}
```

**Step 3: Проверить вручную что файл не сломан**

```bash
cd frontend
# Убедиться что нет синтаксических ошибок (если есть pnpm dev)
# Просто визуально проверить diff
```

**Step 4: Проверить что других `window.location.href` нет**

```bash
grep -r "window.location" frontend/src/
```

Ожидаемый результат: ничего не найдено (или только в других местах, не в client.ts).

---

### Task 2: Создать компонент `AuthWatcher`

**Files:**
- Create: `frontend/src/features/protected-route/ui/AuthWatcher.tsx`
- Modify: `frontend/src/features/protected-route/index.ts`

**Step 1: Создать файл `AuthWatcher.tsx`**

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

    return () => {
      window.removeEventListener('auth:unauthorized', handler);
    };
  }, [navigate, logout]);

  return null;
};
```

**Step 2: Экспортировать из `index.ts`**

Открыть `frontend/src/features/protected-route/index.ts` и добавить экспорт:

```typescript
export { ProtectedRoute } from './ui/ProtectedRoute';
export { AuthWatcher } from './ui/AuthWatcher';
```

**Step 3: Убедиться что импорты корректны**

Проверить что `@entities/auth` экспортирует `useAuthStore`:
```bash
cat frontend/src/entities/auth/index.ts
```
Должна быть строка: `export { useAuthStore } from './model/store';`

---

### Task 3: Подключить `AuthWatcher` в `AdminLayout`

**Files:**
- Modify: `frontend/src/app/layouts/AdminLayout/AdminLayout.tsx`

**Step 1: Прочитать текущий файл**

```tsx
// Текущее содержимое:
import { Outlet } from 'react-router-dom';
import { Box, Flex } from '@chakra-ui/react';
import { AdminHeader } from '@widgets/admin-header';
import { AdminSidebar } from '@widgets/admin-sidebar';

export const AdminLayout = () => (
  <Flex direction="column" minH="100vh">
    <AdminHeader />
    <Flex flex="1">
      <AdminSidebar />
      <Box as="main" flex="1" p={{ base: 4, md: 6, lg: 8 }} bg="bg.canvas">
        <Outlet />
      </Box>
    </Flex>
  </Flex>
);
```

**Step 2: Добавить импорт и компонент**

```tsx
import { Outlet } from 'react-router-dom';
import { Box, Flex } from '@chakra-ui/react';
import { AuthWatcher } from '@features/protected-route';
import { AdminHeader } from '@widgets/admin-header';
import { AdminSidebar } from '@widgets/admin-sidebar';

export const AdminLayout = () => (
  <Flex direction="column" minH="100vh">
    <AuthWatcher />
    <AdminHeader />
    <Flex flex="1">
      <AdminSidebar />
      <Box as="main" flex="1" p={{ base: 4, md: 6, lg: 8 }} bg="bg.canvas">
        <Outlet />
      </Box>
    </Flex>
  </Flex>
);
```

**Почему в `AdminLayout`, а не в `App`:** `useNavigate` требует контекст React Router (`RouterProvider`). `AdminLayout` рендерится внутри роутера, поэтому `useNavigate` работает корректно.

---

### Task 4: Добавить редирект в `LoginPage`

**Files:**
- Modify: `frontend/src/pages/login/ui/LoginPage.tsx`

**Step 1: Прочитать текущий файл**

```tsx
// Текущее содержимое:
import { LoginForm } from '@features/auth-login';

export const LoginPage = () => {
  return <LoginForm />;
};
```

**Step 2: Добавить редирект для авторизованных**

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

**Зачем:** Если у пользователя есть действующий токен и он открывает `/login` — сразу попадает в админку. Исключает ситуацию "кнопка логина нажата, но пользователь уже авторизован".

---

### Task 5: Пересобрать frontend и проверить

**Step 1: Пересобрать Docker образ**

```bash
cd /Users/admin/Documents/project/FAQ_RAG_llm_bot
docker compose build frontend
```

Ожидаемый результат: `Image faq_rag_llm_bot-frontend Built`

**Step 2: Перезапустить контейнер**

```bash
docker compose up -d frontend
```

Ожидаемый результат:
```
Container faq_rag_llm_bot-frontend-1 Recreated
Container faq_rag_llm_bot-frontend-1 Started
```

**Step 3: Проверить что frontend отвечает**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```

Ожидаемый результат: `200`

---

### Task 6: Ручное тестирование

**Тест 1 — Логин работает:**
1. Открыть `http://localhost:3000/login`
2. Ввести `admin@example.com` / `admin123`
3. Нажать кнопку
4. ✅ Ожидаемо: редирект в `/admin/chat`, кнопка не зависает

**Тест 2 — Авто-разлогин при протухших токенах:**
1. Залогиниться
2. Открыть DevTools → Application → Local Storage → `localhost:3000`
3. Удалить `refresh_token` и поменять `access_token` на `invalid`
4. Отправить любой запрос в чате
5. ✅ Ожидаемо: редирект на `/login` без перезагрузки страницы

**Тест 3 — Редирект авторизованного с `/login`:**
1. Залогиниться (действующий токен в localStorage)
2. Вручную перейти на `http://localhost:3000/login`
3. ✅ Ожидаемо: автоматически попадаешь в `/admin`

**Тест 4 — nginx больше не видит 499:**
```bash
docker compose logs frontend --tail=20
```
После успешного логина — только `200` статусы для login POST, никаких `499`.

---

### Контрольный список перед финишем

```
□ client.ts: нет window.location.href
□ AuthWatcher: создан и экспортирован
□ AdminLayout: подключён AuthWatcher
□ LoginPage: редирект для авторизованных
□ docker compose build frontend — прошёл без ошибок
□ Тест 1 (логин) — ✅
□ Тест 2 (авто-разлогин) — ✅
□ Тест 3 (редирект с /login) — ✅
□ Тест 4 (нет 499 в nginx) — ✅
```
