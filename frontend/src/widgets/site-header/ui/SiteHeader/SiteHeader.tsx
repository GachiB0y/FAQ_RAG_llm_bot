import { useIntl } from 'react-intl';
import { NavLink } from 'react-router-dom';
import { Box, Button, Container, Flex, HStack, Text } from '@chakra-ui/react';
import { LocaleSwitcher } from '@features/locale-switcher';
import { ThemeSwitcher } from '@features/theme-switcher';
import { motion, slideDown } from '@shared/lib';
import { HEADER_NAV_LINKS } from '@widgets/site-header/model/constants';

export const SiteHeader = () => {
  const { formatMessage } = useIntl();

  return (
    <motion.div variants={slideDown} initial="hidden" animate="visible">
      <Box as="header" borderBottom="1px solid" borderColor="border.default" bg="bg.surface">
        <Container maxW="7xl" py={4}>
          <Flex align="center" justify="space-between" gap={6} flexWrap="wrap">
            <Text fontWeight="700" letterSpacing="0.04em">
              {formatMessage({ id: 'app.title' })}
            </Text>
            <HStack spacing={4} flexWrap="wrap">
              {HEADER_NAV_LINKS.map((link) => (
                <Button
                  key={link.to}
                  as={NavLink}
                  to={link.to}
                  end={link.to === '/'}
                  size="sm"
                  variant="ghost"
                  _activeLink={{
                    bg: 'bg.subtle',
                    color: 'text.primary',
                  }}
                >
                  {formatMessage({ id: link.labelIntlKey })}
                </Button>
              ))}
              <ThemeSwitcher />
              <LocaleSwitcher />
            </HStack>
          </Flex>
        </Container>
      </Box>
    </motion.div>
  );
};
