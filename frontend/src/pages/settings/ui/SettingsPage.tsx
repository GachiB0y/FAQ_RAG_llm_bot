import { useIntl } from 'react-intl';
import {
  Box,
  Card,
  CardBody,
  Heading,
  VStack,
} from '@chakra-ui/react';
import { SettingsForm } from '@features/settings-form';

export const SettingsPage = () => {
  const { formatMessage } = useIntl();

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        <Heading size="lg">{formatMessage({ id: 'settings.title' })}</Heading>

        <Card>
          <CardBody>
            <SettingsForm />
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};
