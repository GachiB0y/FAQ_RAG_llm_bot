import { useIntl } from 'react-intl';
import {
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  VStack,
} from '@chakra-ui/react';
import { UsersTable } from '@features/users-table';

export const UsersPage = () => {
  const { formatMessage } = useIntl();

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        <Heading size="lg">{formatMessage({ id: 'users.title' })}</Heading>

        <Card>
          <CardHeader>
            <Heading size="md">{formatMessage({ id: 'users.title' })}</Heading>
          </CardHeader>
          <CardBody>
            <UsersTable />
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};
