import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import importPlugin from 'eslint-plugin-import';
import reactPlugin from 'eslint-plugin-react';
import reactHooksPlugin from 'eslint-plugin-react-hooks';
import simpleImportSort from 'eslint-plugin-simple-import-sort';

export default [
  {
    // Полностью исключаем служебные директории и конфиги из проверки ESLint.
    ignores: [
      'dist',
      'node_modules',
      'eslint.config.js',
      'vite.config.ts',
      '.corepack',
      'corepack',
      'pnpm-lock.yaml',
    ],
  },
  {
    // Линтим только TypeScript/TSX-файлы проекта.
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      // Подключаем парсер от typescript-eslint, чтобы ESLint понимал TS-синтаксис.
      parser: tsParser,
      parserOptions: {
        // Используем настройки из основного tsconfig.
        project: './tsconfig.json',
        // Говорим парсеру, что корень tsconfig совпадает с расположением этого файла.
        tsconfigRootDir: import.meta.dirname,
      },
      globals: {
        // Добавляем глобальные переменные браузера (window, document и т.д.).
        ...globals.browser,
        // Добавляем глобальные переменные Node.js (process, __dirname и т.д.).
        ...globals.node,
      },
    },
    plugins: {
      // Правила для TypeScript (типобезопасность, best practices).
      '@typescript-eslint': tsPlugin,
      // Проверки React-специфичных шаблонов (jsx, props и т.д.).
      react: reactPlugin,
      // Отдельные проверки корректного использования React Hooks.
      'react-hooks': reactHooksPlugin,
      // Контроль импортов (дубли, невыполненные зависимости, порядок).
      import: importPlugin,
      // Автосортировка импортов и экспортов.
      'simple-import-sort': simpleImportSort,
    },
    settings: {
      react: {
        // Версию React определяем автоматически по установленной зависимости.
        version: 'detect',
      },
      'import/resolver': {
        // Разрешаем алиасы и пути из tsconfig при анализе импортов.
        typescript: true,
      },
    },
    rules: {
      // В современном React не требуется импортировать React ради JSX.
      'react/react-in-jsx-scope': 'off',
      // Аналогичное правило о неиспользуемом React в JSX — отключаем.
      'react/jsx-uses-react': 'off',
      // Разрешаем JSX только в .tsx файлах, чтобы не смешивать его с TS без JSX.
      'react/jsx-filename-extension': ['error', { extensions: ['.tsx'] }],
      // Используем TypeScript вместо prop-types.
      'react/prop-types': 'off',
      // Inline-стили запрещены: используем Chakra props или SCSS-модули.
      'react/forbid-component-props': [
        'error',
        {
          forbid: ['style'],
        },
      ],
      // Обязываем использовать type-only импорты там, где передаются только типы.
      '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
      // Тип возвращаемого значения функций выводим автоматически.
      '@typescript-eslint/explicit-function-return-type': 'off',
      // Запрещаем оставлять незакрытые промисы без await/catch.
      '@typescript-eslint/no-floating-promises': 'error',
      // `any` запрещён. Если нужно, используем `unknown` и приводим к типу явно.
      '@typescript-eslint/no-explicit-any': 'error',
      // Не ругаемся на переменные/аргументы, начинающиеся с _, считая их умышленно неиспользуемыми.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // Прописываем обязательные отступы в 2 пробела, чтобы подсвечивать «странные» отступы.
      indent: [
        'error',
        2,
        {
          SwitchCase: 1,
          // JSX анализируем отдельными правилами react/jsx-indent*, поэтому исключаем его здесь.
          ignoredNodes: ['JSXElement', 'JSXElement *'],
        },
      ],
      // Контролируем отступы в JSX-деревьях.
      'react/jsx-indent': ['error', 2],
      // И отдельно для пропсов/атрибутов.
      'react/jsx-indent-props': ['error', 2],
      // Запрещаем default-экспорты, чтобы код соответствовал FSD-структуре.
      'import/no-default-export': 'error',
      // Отключаем встроенный порядок импортов, так как используем simple-import-sort.
      'import/order': 'off',
      // Требуем упорядоченные импорты по группам (вверху файла).
      'simple-import-sort/imports': [
        'error',
        {
          groups: [
            // 1) Пакеты React и прочие внешние зависимости.
            ['^react', '^@?\\w'],
            // 2) Проектные алиасы/абсолютные импорты (FSD-слои).
            ['^(@|src)(/.*|$)'],
            // 3) Родственные импорты на уровень выше.
            ['^\\.\\.(?!/?$)', '^\\.\\./?$'],
            // 4) Относительные импорты внутри текущего модуля.
            ['^\\./(?=.*/)(?!/?$)', '^\\.(?!/?$)', '^\\./?$'],
            // 5) Типы/side-effect импорты (simple-import-sort помечает их \u0000).
            ['^\\u0000'],
            // 6) Стили — всегда в самом конце блока импортов.
            ['^.+\\.s?css$'],
          ],
        },
      ],
      // Требуем упорядоченные экспорты (внизу файла).
      'simple-import-sort/exports': 'error',
    },
  },
  {
    // Дополнительные ограничения на структуру импортов во всех TS/TSX файлах.
    files: ['**/*.ts', '**/*.tsx'],
    rules: {
      // Запрещаем подниматься по относительным путям (../), чтобы форсить абсолютные алиасы.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['../*'],
              message: 'Используйте абсолютные алиасы FSD вместо относительных подъёмов.',
            },
          ],
        },
      ],
    },
  },
];
