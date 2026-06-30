# Инструкции по развитию проекта

## Стек и версии

| Модуль            | Версия  | Комментарий                                  |
| ----------------- | ------- | -------------------------------------------- |
| React / React DOM | 19.2.0  | Функциональные компоненты, strict mode       |
| Vite              | 7.2.4   | Быстрая dev-сборка, alias в `vite.config.ts` |
| Chakra UI         | 2.8.2   | Tree-shaking, темизация в `theme.ts`         |
| Zustand           | 5.0.8   | Локальные сторы на уровне сущностей/фич      |
| React Query       | 5.90.11 | `queryClient` в `shared/config/query`        |
| React Router DOM  | 7.9.6   | SPA-маршруты через `createBrowserRouter`     |
| axios             | 1.13.2  | HTTP-клиент `shared/api/httpClient.ts`       |
| react-intl        | 7.1.14  | Локализация + хуки `useIntl`                 |

Все зависимости жёстко зафиксированы в `package.json`. Добавляя новые пакеты - используйте `pnpm add -E` / `pnpm add -D -E`.

## Архитектура (FSD)

1. **shared** - UI-кирпичики, утилиты, конфиги (axios, i18n, query)
2. **entities** - бизнес-сущности и их сторы (`settings` уже создана)
3. **features** - пользовательские сценарии (пример: `locale-switcher`)
4. **widgets** - композиции нескольких фич
5. **pages** - готовые страницы / маршруты
6. **app** - провайдеры, роутинг, глобальные стили

Каждый слой экспортирует публичный API через `index.ts`. Внутренние файлы запрещено импортировать напрямую из других слоёв.

## Стили

- Глобальные стили: `app/styles/index.scss`
- Локальные стили: только SCSS-модули (`*.module.scss`)
- Для сложных компонентов используйте токены Chakra (цвета, spacing) + `className` для модулей

## Локализация

1. Добавляйте ключи в `shared/config/i18n/locales/*.json`
2. Экспортируйте локаль через `messages` / `SUPPORTED_LOCALES`
3. Используйте Реакт-хуки `useIntl()` и `formatMessage` (см. `.cursor/rules/stack-i18n.mdc`)
4. Для смены языка сохраняйте выбор в zustand-сторе (`entities/settings`)
5. Строки вне компонентов принимают `IntlShape` в аргументах
6. Для автоматической синхронизации ключей используйте `pnpm i18n:sync` (добавит отсутствующие id во все JSON с плейсхолдерами)

## React Query + Axios

- Все запросы оформляем в хуках `useSomethingQuery/Mutation`
- Query keys — массивы, вынесенные рядом с хуком; invalidate происходит через эти helpers
- HTTP-клиент один (`shared/api/httpClient.ts`); при необходимости добавляем интерсепторы
- Отдельные опции (`retry`, `staleTime`) меняем только если описали причину в правилах фичи
- Подробные требования: `.cursor/rules/stack-data.mdc`

## Маршрутизация

- Используем [react-router-dom 7](https://reactrouter.com/en/main) и `createBrowserRouter`
- Корневой layout (`RootLayout`) живёт в `app/layouts`, страницы — в `pages`
- Новые маршруты добавляем в `app/providers/router.tsx` и документируем
- Навигацию выполняем через `Link`/`NavLink` или `useNavigate`, ссылки на правила: `.cursor/rules/stack-routing.mdc`

## Качество кода

- ESLint конфиг c правилами FSD (`import/no-default-export`, запрет `../`)
- Prettier контролирует форматирование
- Husky + lint-staged гарантируют чистый код перед коммитом

## Правила Cursor

- Каталог с полной структурой и ссылками: `docs/rules/README.md`.
- Все project-rules лежат в `.cursor/rules/*.mdc` (формат [MDC](https://cursor.com/ru/docs/context/rules)).
- Для фич создаём вложенные каталоги `.cursor/rules` прямо внутри слоя (пример: `src/features/locale-switcher/.cursor/rules/locale-switcher.mdc`).
- В `globs` или вложенных каталогах указываем область действия. Более глубокие правила имеют приоритет над корневыми.
- Любое изменение в рабочем процессе сопровождаем обновлением соответствующего `.mdc` и ссылкой на официальную документацию.

## Чеклист перед добавлением новой фичи

- [ ] Создан `feature-name/index.ts` c экспортами
- [ ] Стор / API - в слое entities/shared
- [ ] Стили - SCSS-модуль
- [ ] Добавлены строки локализации (если требуется)
- [ ] Пройдены `pnpm lint` и `pnpm typecheck`
