import { useIntl } from 'react-intl';
import {
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  VStack,
} from '@chakra-ui/react';
import { DocumentUpload } from '@features/document-upload';
import { DocumentsTable } from '@features/documents-table';

export const DocumentsPage = () => {
  const { formatMessage } = useIntl();

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        <Heading size="lg">{formatMessage({ id: 'documents.title' })}</Heading>

        <Card>
          <CardHeader>
            <Heading size="md">{formatMessage({ id: 'documents.upload.title' })}</Heading>
          </CardHeader>
          <CardBody>
            <DocumentUpload />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <Heading size="md">{formatMessage({ id: 'documents.list.title' })}</Heading>
          </CardHeader>
          <CardBody>
            <DocumentsTable />
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};
