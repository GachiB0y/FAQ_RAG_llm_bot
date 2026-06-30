import type { SupportedLocale } from '@shared/config/i18n';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from '@shared/config/i18n';
import { create } from 'zustand';

const isSupportedLocale = (value: string): value is SupportedLocale =>
  (SUPPORTED_LOCALES as readonly string[]).includes(value);

const detectLocale = (): SupportedLocale => {
  if (typeof navigator === 'undefined') {
    return DEFAULT_LOCALE;
  }

  const browserLocale = navigator.language?.slice(0, 2).toLowerCase();

  if (isSupportedLocale(browserLocale)) {
    return browserLocale;
  }

  return DEFAULT_LOCALE;
};

export type SettingsState = {
  locale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
};

export const useSettingsStore = create<SettingsState>((set) => ({
  locale: detectLocale(),
  setLocale: (locale) => set({ locale }),
}));
