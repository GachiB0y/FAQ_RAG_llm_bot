#!/usr/bin/env node
import fg from 'fast-glob';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const PROJECT_ROOT = new URL('..', import.meta.url).pathname;
const SOURCE_GLOBS = ['src/**/*.{ts,tsx}'];
const IGNORE_GLOBS = ['**/*.d.ts', '**/*.spec.*', '**/*.test.*'];
const ID_REGEX = /formatMessage\s*\(\s*\{\s*id:\s*['"`]([^'"`]+)['"`]/g;
const LOCALES_DIR = path.resolve(PROJECT_ROOT, 'src/shared/config/i18n/locales');

const log = (msg) => console.log(`[i18n-sync] ${msg}`);

const collectIds = async () => {
  const files = await fg(SOURCE_GLOBS, {
    ignore: IGNORE_GLOBS,
    cwd: PROJECT_ROOT,
    absolute: true,
  });

  const ids = new Set();

  for (const filePath of files) {
    const content = await readFile(filePath, 'utf8');
    let match;
    while ((match = ID_REGEX.exec(content))) {
      ids.add(match[1]);
    }
  }

  if (ids.size === 0) {
    log('Не найдено ни одного formatMessage id.');
  }

  return Array.from(ids).sort();
};

const syncLocale = async (localeFile, ids) => {
  const localePath = path.join(LOCALES_DIR, localeFile);
  const raw = await readFile(localePath, 'utf8');
  const json = JSON.parse(raw);

  let updated = false;

  for (const id of ids) {
    if (!(id in json)) {
      json[id] = `TODO: ${id}`;
      updated = true;
    }
  }

  const sorted = Object.keys(json)
    .sort()
    .reduce((acc, key) => {
      acc[key] = json[key];
      return acc;
    }, {});

  if (updated) {
    await writeFile(localePath, `${JSON.stringify(sorted, null, 2)}\n`);
    log(`Обновлён ${localeFile}`);
  } else {
    log(`${localeFile} — без изменений`);
  }
};

const main = async () => {
  const ids = await collectIds();
  if (!ids.length) {
    return;
  }

  const localeFiles = await fg('*.json', { cwd: LOCALES_DIR });
  await Promise.all(localeFiles.map((file) => syncLocale(file, ids)));

  log(`Синхронизация завершена. Найдено ${ids.length} id.`);
};

main().catch((error) => {
  console.error('[i18n-sync] Ошибка:', error);
  process.exitCode = 1;
});
