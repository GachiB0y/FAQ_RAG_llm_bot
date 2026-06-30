import { useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import { Box, Button, Flex, HStack, Text } from '@chakra-ui/react';
import { LocaleSwitcher } from '@features/locale-switcher';
import { ThemeSwitcher } from '@features/theme-switcher';
import { authApi } from '@shared/api';

export const AdminHeader = () => {
  const { formatMessage } = useIntl();
  const navigate = useNavigate();

  const handleLogout = () => {
    authApi.logout();
    navigate('/login');
  };

  return (
    <Box
      as="header"
      borderBottom="1px solid"
      borderColor="border.default"
      bg="bg.surface"
      px={6}
      py={4}
    >
      <Flex align="center" justify="space-between">
        <Text fontWeight="700" fontSize="lg" letterSpacing="0.04em">
          {formatMessage({ id: 'admin.title' })}
        </Text>
        <HStack spacing={4}>
          <ThemeSwitcher />
          <LocaleSwitcher />
          <Button size="sm" variant="outline" onClick={handleLogout}>
            {formatMessage({ id: 'nav.logout' })}
          </Button>
        </HStack>
      </Flex>
    </Box>
  );
};
