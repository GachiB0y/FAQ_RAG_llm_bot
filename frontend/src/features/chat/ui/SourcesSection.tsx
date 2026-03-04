import { useIntl } from 'react-intl';
import {
  Box,
  Button,
  Collapse,
  Text,
  useDisclosure,
  VStack,
} from '@chakra-ui/react';
import type { ChatSource } from '@shared/api';

interface SourcesSectionProps {
  sources: ChatSource[];
}

export const SourcesSection = ({ sources }: SourcesSectionProps) => {
  const { formatMessage } = useIntl();
  const { isOpen, onToggle } = useDisclosure();

  return (
    <Box mt={1}>
      <Button variant="link" size="xs" onClick={onToggle} colorScheme="gray">
        {formatMessage({ id: 'chat.sources' })} ({sources.length})
      </Button>
      <Collapse in={isOpen}>
        <VStack
          align="start"
          spacing={1}
          mt={1}
          pl={2}
          borderLeftWidth="2px"
          borderColor="gray.300"
        >
          {sources.map((source, idx) => (
            <Text key={idx} fontSize="xs" color="gray.500">
              {source.document}
              {source.page != null ? ` (p. ${source.page})` : ''}
            </Text>
          ))}
        </VStack>
      </Collapse>
    </Box>
  );
};
