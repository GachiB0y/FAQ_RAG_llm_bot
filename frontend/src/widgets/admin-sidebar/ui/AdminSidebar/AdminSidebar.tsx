import { useIntl } from 'react-intl';
import { NavLink } from 'react-router-dom';
import { Box, Button, VStack } from '@chakra-ui/react';
import { ADMIN_NAV_LINKS } from '@widgets/admin-sidebar/model/constants';

export const AdminSidebar = () => {
  const { formatMessage } = useIntl();

  return (
    <Box
      as="nav"
      aria-label={formatMessage({ id: 'nav.admin.label' })}
      w={{ base: '200px', lg: '250px' }}
      minH="100%"
      bg="bg.subtle"
      borderRight="1px solid"
      borderColor="border.default"
      py={6}
      px={4}
    >
      <VStack spacing={2} align="stretch">
        {ADMIN_NAV_LINKS.map((link) => (
          <Button
            key={link.to}
            as={NavLink}
            to={link.to}
            justifyContent="flex-start"
            size="md"
            variant="ghost"
            fontWeight="normal"
            _activeLink={{
              bg: 'bg.muted',
              color: 'text.primary',
              fontWeight: 'semibold',
            }}
          >
            {formatMessage({ id: link.labelIntlKey })}
          </Button>
        ))}
      </VStack>
    </Box>
  );
};
