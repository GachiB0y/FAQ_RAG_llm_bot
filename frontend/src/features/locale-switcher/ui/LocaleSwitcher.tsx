import { useIntl } from 'react-intl';
import { Select } from '@chakra-ui/react';
import { useSettingsStore } from '@entities/settings';
import { SUPPORTED_LOCALES, type SupportedLocale } from '@shared/config/i18n';

export const LocaleSwitcher = () => {
  const { formatMessage } = useIntl();
  const locale = useSettingsStore((state) => state.locale);
  const setLocale = useSettingsStore((state) => state.setLocale);

  return (
    <Select
      maxW="200px"
      value={locale}
      aria-label={formatMessage({ id: 'action.locale' })}
      onChange={(event) => setLocale(event.target.value as SupportedLocale)}
      size="sm"
      variant="filled"
    >
      {SUPPORTED_LOCALES.map((value) => (
        <option key={value} value={value}>
          {value.toUpperCase()}
        </option>
      ))}
    </Select>
  );
};
