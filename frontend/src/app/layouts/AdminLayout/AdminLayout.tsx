import { Outlet } from 'react-router-dom';
import { Box, Flex } from '@chakra-ui/react';
import { AuthWatcher } from '@features/protected-route';
import { AdminHeader } from '@widgets/admin-header';
import { AdminSidebar } from '@widgets/admin-sidebar';

export const AdminLayout = () => (
  <Flex direction="column" minH="100vh">
    <AuthWatcher />
    <AdminHeader />
    <Flex flex="1">
      <AdminSidebar />
      <Box as="main" flex="1" p={{ base: 4, md: 6, lg: 8 }} bg="bg.canvas">
        <Outlet />
      </Box>
    </Flex>
  </Flex>
);
