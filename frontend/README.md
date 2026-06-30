# Cursor Instructions Starter

Современный каркас для написания инструкций и примеров под Cursor. Стек: React + Vite + TypeScript, Chakra UI, Zustand, React Query, axios, SCSS-модули и локализация через `react-intl`.

## Основные фичи

- **Vite + React 19** - быстрый dev-server и build
- **Chakra UI** - лёгкая UI-библиотека с трешейкингом и кастомизацией
- **Feature-Sliced Design** - жёсткая модульность и слойность
- **React Router 7** - рендерим страницы через `createBrowserRouter`
- **Zustand** - сторы на уровне фич и сущностей
- **react-intl hooks** - локализация через `useIntl`
- **React Query + axios** - типизированные `useSomethingQuery/Mutation`
- **ESLint + Prettier + Husky** - автоматический контроль кодстайла

## Структура проекта (FSD)

```
src/
├─ app/        # точка входа, глобальные провайдеры, темы
├─ pages/      # страницы и маршруты
├─ widgets/    # композиции фич
├─ features/   # пользовательские сценарии
├─ entities/   # бизнес-сущности и их состояние
└─ shared/     # переиспользуемые утилиты, UI, конфиги
```

## Команды

- `pnpm dev` - локальная разработка
- `pnpm build` - production-сборка
- `pnpm preview` - предпросмотр билда
- `pnpm lint` / `pnpm lint:fix` - ESLint (FSD правила + import sorting)
- `pnpm format` / `pnpm format:check` - Prettier
- `pnpm typecheck` - проверка типов без сборки
- `pnpm i18n:sync` - собрать все `formatMessage` id и заполнить JSON локалей плейсхолдерами

Перед коммитом Husky запускает `lint-staged`, который автоматически прогоняет ESLint и Prettier только по изменённым файлам.

## Что настроено

- алиасы `@app`, `@pages`, `@features`, `@entities`, `@shared`
- ChakraProvider + QueryClientProvider + IntlProvider в `AppProviders`
- пример сторы `settings` (zustand) и фичи `LocaleSwitcher`
- axios-инстанс `httpClient`
- глобальные SCSS-стили и пример SCSS-модуля
- каталоги локализаций (`src/shared/config/i18n/locales`)

## Дальнейшие шаги

1. Добавляйте новые сущности/фичи, публикуя только публичный API (index.ts)
2. Для сетевых вызовов используйте `httpClient` + React Query hooks в слое features/widgets
3. Расширяйте локализации, добавляя строки в JSON и используя `formatMessage`
4. Поддерживайте единый кодстайл: все изменения проходят через `pnpm lint-staged`
