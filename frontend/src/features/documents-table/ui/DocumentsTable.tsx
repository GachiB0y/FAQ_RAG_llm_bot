import { useRef } from 'react';
import { useIntl } from 'react-intl';
import { DeleteIcon, RepeatIcon } from '@chakra-ui/icons';
import {
  Alert,
  AlertIcon,
  Badge,
  HStack,
  IconButton,
  Skeleton,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  useToast,
} from '@chakra-ui/react';
import type { Document } from '@entities/document';
import { useDeleteDocument, useDocuments, useReplaceDocument } from '@entities/document';

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const StatusBadge = ({ status }: { status: Document['status'] }) => {
  const colorScheme = {
    processing: 'yellow',
    ready: 'green',
    error: 'red',
  }[status];

  return <Badge colorScheme={colorScheme}>{status}</Badge>;
};

export const DocumentsTable = () => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replaceIdRef = useRef<string | null>(null);

  const { data, isLoading, error } = useDocuments();
  const deleteMutation = useDeleteDocument();
  const replaceMutation = useReplaceDocument();

  const handleDelete = async (id: string, name: string) => {
    if (window.confirm(formatMessage({ id: 'documents.delete.confirm' }, { name }))) {
      try {
        await deleteMutation.mutateAsync(id);
        toast({
          title: formatMessage({ id: 'documents.delete.success' }),
          status: 'success',
          duration: 3000,
        });
      } catch {
        toast({
          title: formatMessage({ id: 'documents.delete.error' }),
          status: 'error',
          duration: 3000,
        });
      }
    }
  };

  const handleReplaceClick = (id: string) => {
    replaceIdRef.current = id;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && replaceIdRef.current) {
      try {
        await replaceMutation.mutateAsync({ id: replaceIdRef.current, file });
        toast({
          title: formatMessage({ id: 'documents.replace.success' }),
          status: 'success',
          duration: 3000,
        });
      } catch {
        toast({
          title: formatMessage({ id: 'documents.replace.error' }),
          status: 'error',
          duration: 3000,
        });
      }
      replaceIdRef.current = null;
      e.target.value = '';
    }
  };

  if (isLoading) {
    return (
      <>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} height="50px" mb={2} />
        ))}
      </>
    );
  }

  if (error) {
    return (
      <Alert status="error">
        <AlertIcon />
        {formatMessage({ id: 'documents.error.load' })}
      </Alert>
    );
  }

  if (!data?.items.length) {
    return (
      <Alert status="info">
        <AlertIcon />
        {formatMessage({ id: 'documents.empty' })}
      </Alert>
    );
  }

  return (
    <>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".txt,.md,.html,.pdf,.docx,.xlsx"
        onChange={handleFileChange}
      />
      <Table variant="simple">
        <Thead>
          <Tr>
            <Th>{formatMessage({ id: 'documents.table.name' })}</Th>
            <Th>{formatMessage({ id: 'documents.table.type' })}</Th>
            <Th>{formatMessage({ id: 'documents.table.size' })}</Th>
            <Th>{formatMessage({ id: 'documents.table.chunks' })}</Th>
            <Th>{formatMessage({ id: 'documents.table.status' })}</Th>
            <Th>{formatMessage({ id: 'documents.table.updated' })}</Th>
            <Th>{formatMessage({ id: 'documents.table.actions' })}</Th>
          </Tr>
        </Thead>
        <Tbody>
          {data.items.map((doc) => (
            <Tr key={doc.id}>
              <Td>
                <Text fontWeight="medium">{doc.original_name}</Text>
              </Td>
              <Td>{doc.file_type.toUpperCase()}</Td>
              <Td>{formatFileSize(doc.file_size)}</Td>
              <Td>{doc.chunk_count}</Td>
              <Td><StatusBadge status={doc.status} /></Td>
              <Td>{new Date(doc.updated_at).toLocaleDateString()}</Td>
              <Td>
                <HStack spacing={2}>
                  <IconButton
                    aria-label={formatMessage({ id: 'documents.action.replace' })}
                    icon={<RepeatIcon />}
                    size="sm"
                    variant="ghost"
                    onClick={() => handleReplaceClick(doc.id)}
                    isLoading={replaceMutation.isPending}
                  />
                  <IconButton
                    aria-label={formatMessage({ id: 'documents.action.delete' })}
                    icon={<DeleteIcon />}
                    size="sm"
                    variant="ghost"
                    colorScheme="red"
                    onClick={() => handleDelete(doc.id, doc.original_name)}
                    isLoading={deleteMutation.isPending}
                  />
                </HStack>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </>
  );
};
