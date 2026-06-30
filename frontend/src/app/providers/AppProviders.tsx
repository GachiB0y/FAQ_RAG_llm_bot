import type { ReactNode } from 'react';
import { IntlProvider } from 'react-intl';
import { ChakraProvider, ColorModeScript } from '@chakra-ui/react';
import { useSettingsStore } from '@entities/settings';
import { messages } from '@shared/config/i18n';
import { queryClient } from '@shared/config/query';
import { QueryClientProvider } from '@tanstack/react-query';

import { theme } from './theme';

type Props = {
  children: ReactNode;
};

export const AppProviders = ({ children }: Props) => {
  const locale = useSettingsStore((state) => state.locale);

  return (
    <>
      <ColorModeScript initialColorMode={theme.config.initialColorMode} />
      <ChakraProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <IntlProvider locale={locale} messages={messages[locale]}>
            {children}
          </IntlProvider>
        </QueryClientProvider>
      </ChakraProvider>
    </>
  );
};
