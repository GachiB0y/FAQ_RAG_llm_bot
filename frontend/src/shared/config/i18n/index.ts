import en from './locales/en.json';
import ru from './locales/ru.json';

export const SUPPORTED_LOCALES = ['en', 'ru'] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: SupportedLocale = 'en';

export const messages: Record<SupportedLocale, Record<string, string>> = {
  en,
  ru,
};
