import { Outlet } from 'react-router-dom';
import { Box } from '@chakra-ui/react';
import { SiteHeader } from '@widgets/site-header';

import styles from './RootLayout.module.scss';

export const RootLayout = () => (
  <Box className={styles.app} data-testid="app-root">
    <SiteHeader />
    <Box as="main" flex="1" py={{ base: 8, md: 12 }}>
      <Outlet />
    </Box>
  </Box>
);
