import { useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { AddIcon } from '@chakra-ui/icons';
import {
  Box,
  Button,
  Progress,
  Text,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { useUploadDocument } from '@entities/document';

const ALLOWED_TYPES = ['.txt', '.md', '.html', '.pdf', '.docx', '.xlsx'];

export const DocumentUpload = () => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const uploadMutation = useUploadDocument();

  const handleUpload = async (file: File) => {
    try {
      await uploadMutation.mutateAsync(file);
      toast({
        title: formatMessage({ id: 'documents.upload.success' }),
        status: 'success',
        duration: 3000,
      });
    } catch {
      toast({
        title: formatMessage({ id: 'documents.upload.error' }),
        status: 'error',
        duration: 3000,
      });
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleUpload(file);
      e.target.value = '';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleUpload(file);
    }
  };

  return (
    <VStack spacing={4} align="stretch">
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept={ALLOWED_TYPES.join(',')}
        onChange={handleFileChange}
      />

      <Box
        p={8}
        border="2px dashed"
        borderColor={isDragging ? 'blue.400' : 'gray.300'}
        borderRadius="lg"
        textAlign="center"
        bg={isDragging ? 'blue.50' : 'transparent'}
        _dark={{ bg: isDragging ? 'blue.900' : 'transparent' }}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        cursor="pointer"
        onClick={() => fileInputRef.current?.click()}
      >
        <VStack spacing={2}>
          <AddIcon boxSize={8} color="gray.400" />
          <Text fontWeight="medium">
            {formatMessage({ id: 'documents.upload.dragdrop' })}
          </Text>
          <Text fontSize="sm" color="gray.500">
            {formatMessage({ id: 'documents.upload.formats' })}
          </Text>
        </VStack>
      </Box>

      {uploadMutation.isPending && (
        <Progress size="sm" isIndeterminate colorScheme="blue" />
      )}

      <Button
        leftIcon={<AddIcon />}
        colorScheme="blue"
        onClick={() => fileInputRef.current?.click()}
        isLoading={uploadMutation.isPending}
      >
        {formatMessage({ id: 'documents.upload.button' })}
      </Button>
    </VStack>
  );
};
