# Project Instructions for Claude

Этот проект использует Feature-Sliced Design (FSD) архитектуру с React, TypeScript, Chakra UI, React Query и react-intl.

## Документация проекта

Все правила и инструкции для работы с проектом находятся в папке `.claude/`:

### Правила (Rules)

Правила описывают **что** должно быть в проекте — архитектурные решения, стандарты кода, требования к фичам.

- **[Rules Index](.claude/rules/rules-index.md)** — главный навигатор по всем правилам

#### Core

- [Project Architecture](.claude/rules/core/project-architecture.md) — FSD-иерархия, алиасы, слои
- [Code Style](.claude/rules/core/code-style.md) — SOLID/KISS/DRY, паттерны, хуки

#### Stack

- [UI Stack](.claude/rules/stack/stack-ui.md) — Chakra UI, SCSS-модули
- [Theme Tokens](.claude/rules/stack/stack-theme-tokens.md) — дизайн-система, токены
- [Data Layer](.claude/rules/stack/stack-data.md) — React Query + axios
- [i18n](.claude/rules/stack/stack-i18n.md) — react-intl, локализация
- [Routing](.claude/rules/stack/stack-routing.md) — react-router v7
- [Accessibility](.claude/rules/stack/stack-accessibility.md) — доступность, брейкпоинты
- [Animations](.claude/rules/stack/stack-animations.md) — framer-motion

#### Tooling

- [Linting](.claude/rules/tooling/tooling-linting.md) — ESLint, Prettier, Husky
- [Git Workflow](.claude/rules/tooling/git-workflow.md) — один коммит на MR
- [Rules Registry](.claude/rules/tooling/rules-registry.md) — как добавлять правила

#### Agent

- [Agent Ops](.claude/rules/agent/agent-ops.md) — как работать с правилами
- [Interaction Flow](.claude/rules/agent/agent-interaction.md) — планирование и согласование
- [Figma Inputs](.claude/rules/agent/agent-figma.md) — работа с макетами

### Навыки (Skills)

Навыки описывают **как** выполнять типовые задачи — пошаговые инструкции и шаблоны.

- **[Skills Index](.claude/skills/skills-index.md)** — главный навигатор по всем навыкам

#### Setup

- [Setup FSD Project](.claude/skills/setup/setup-fsd-project.md)
- [Setup React Query + Axios](.claude/skills/setup/setup-react-query-axios.md)
- [Setup i18n](.claude/skills/setup/setup-i18n.md)
- [Setup Git Workflow](.claude/skills/setup/setup-git-workflow.md)
- [Setup Zustand Store Patterns](.claude/skills/setup/setup-zustand-store-patterns.md)
- [Setup CI Checks](.claude/skills/setup/setup-ci-checks.md)

#### Create

- [Create Feature](.claude/skills/create/create-feature.md)
- [Create Page](.claude/skills/create/create-page.md)
- [Create Entity](.claude/skills/create/create-entity-skeleton.md)
- [Create Widget](.claude/skills/create/create-widget-composition.md)
- [Create Table with Pagination](.claude/skills/create/create-table-with-pagination.md)
- [Create Switcher Component](.claude/skills/create/create-switcher-component.md)
- [Create Form with Validation](.claude/skills/create/create-form-with-validation.md)
- [Create Auth Flow](.claude/skills/create/create-auth-flow.md)
- [Create Accessible Dialog](.claude/skills/create/create-accessible-dialog.md)
- [Create List + Details Pattern](.claude/skills/create/create-list-details-pattern.md)
- [Create Optimistic Mutation](.claude/skills/create/create-optimistic-mutation.md)

#### Configure

- [Create Feature Rule](.claude/skills/configure/create-feature-rule.md)
- [Create Feature Tech Spec](.claude/skills/configure/create-feature-tech-spec.md)

#### Refactor

- [Refactor Texts to i18n](.claude/skills/refactor/refactor-texts-to-i18n.md)

## Быстрый старт

### Основные команды

```bash
pnpm dev        # Запуск dev-сервера
pnpm build      # Сборка проекта
pnpm lint       # Проверка линтером
pnpm typecheck  # Проверка типов
pnpm format     # Форматирование кода
```

### Ключевые принципы

1. **FSD архитектура**: `shared → entities → features → widgets → pages → app`
2. **Импорты через алиасы**: `@shared`, `@entities`, `@features`, `@widgets`, `@pages`, `@app`
3. **Локализация**: все тексты через `formatMessage` из react-intl
4. **Темизация**: Chakra semantic tokens с `_light` и `default` значениями
5. **Типизация**: никаких `any`, все данные типизированы
6. **Один файл — один компонент**: максимум 200 строк

### Перед каждым PR

1. `pnpm lint` — без ошибок
2. `pnpm typecheck` — без ошибок
3. Один коммит на MR (squash если несколько)
4. Проверить `pnpm dev` на обеих локалях и темах

## Структура проекта

```
src/
├── app/          # Провайдеры, роутер, тема, глобальные стили
├── pages/        # Страницы приложения
├── widgets/      # Композиции фич (header, sidebar, etc.)
├── features/     # Пользовательские сценарии (theme-switcher, posts-table)
├── entities/     # Бизнес-сущности (post, settings)
└── shared/       # Переиспользуемые утилиты, UI-kit, конфиги
    ├── api/      # HTTP-клиент
    ├── config/   # Конфигурация (i18n, query)
    ├── lib/      # Утилиты
    └── ui/       # Базовые UI-компоненты
```

## Как использовать документацию

При работе над задачей:

1. **Прочитай релевантные правила** из `.claude/rules/` для понимания требований
2. **Используй навыки** из `.claude/skills/` как пошаговые инструкции
3. **Создай правило** для новой фичи/страницы, если её ещё нет
4. **Ссылайся на правила** в ответах, когда они влияют на решение
