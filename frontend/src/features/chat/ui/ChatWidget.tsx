import { useCallback, useEffect, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import {
  Badge,
  Box,
  Button,
  Collapse,
  Flex,
  IconButton,
  Input,
  Spinner,
  Text,
  useDisclosure,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { useChatHistory,useSendMessage } from '@features/chat/model';
import type { ChatSource } from '@shared/api';

interface ChatMessageItem {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  confidence?: number;
  created_at?: string;
}

const SourcesSection = ({ sources }: { sources: ChatSource[] }) => {
  const { formatMessage } = useIntl();
  const { isOpen, onToggle } = useDisclosure();

  return (
    <Box mt={1}>
      <Button variant="link" size="xs" onClick={onToggle} colorScheme="gray">
        {formatMessage({ id: 'chat.sources' })} ({sources.length})
      </Button>
      <Collapse in={isOpen}>
        <VStack align="start" spacing={1} mt={1} pl={2} borderLeftWidth="2px" borderColor="gray.300">
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

export const ChatWidget = () => {
  const { formatMessage } = useIntl();
  const toast = useToast();
  const [localMessages, setLocalMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const prevScrollHeightRef = useRef(0);

  const mutation = useSendMessage();
  const {
    data: historyData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isHistoryLoading,
  } = useChatHistory();

  // On initial history load — populate localMessages and scroll to bottom
  useEffect(() => {
    if (!historyData || historyLoaded) return;

    const allPages = historyData.pages;
    if (allPages.length === 0) {
      setHistoryLoaded(true);
      return;
    }

    // Pages: page[0] = most recent (offset=0), page[1] = older, etc.
    // Each page already in chronological order (reversed in service layer).
    // Final display order: oldest first → reverse pages, keep messages within each page as-is.
    const historicMessages: ChatMessageItem[] = allPages
      .slice()
      .reverse()
      .flatMap((page) =>
        page.messages.map((msg) => ({
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          created_at: msg.created_at,
        }))
      );

    setLocalMessages(historicMessages);
    setHistoryLoaded(true);
  }, [historyData, historyLoaded]);

  // After initial history loads — scroll to bottom once
  useEffect(() => {
    if (historyLoaded && !isFetchingNextPage) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    }
  }, [historyLoaded]);

  // After loading older page — prepend to display and restore scroll position
  useEffect(() => {
    if (!historyData || !historyLoaded) return;
    const allPages = historyData.pages;
    if (allPages.length <= 1) return;

    const historicMessages: ChatMessageItem[] = allPages
      .slice()
      .reverse()
      .flatMap((page) =>
        page.messages.map((msg) => ({
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          created_at: msg.created_at,
        }))
      );
    setLocalMessages(historicMessages);

    // Restore scroll position after prepend
    if (scrollAreaRef.current && !isFetchingNextPage) {
      const newScrollHeight = scrollAreaRef.current.scrollHeight;
      scrollAreaRef.current.scrollTop = newScrollHeight - prevScrollHeightRef.current;
    }
  }, [historyData?.pages.length, isFetchingNextPage, historyLoaded]);

  // Scroll to bottom when new messages from user/assistant arrive
  useEffect(() => {
    if (historyLoaded) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [localMessages.length, historyLoaded]);

  // Infinite scroll: load older messages when scrolled to top
  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const el = e.currentTarget;
      if (el.scrollTop === 0 && hasNextPage && !isFetchingNextPage) {
        prevScrollHeightRef.current = el.scrollHeight;
        void fetchNextPage();
      }
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage],
  );

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || mutation.isPending) return;

    const userMessage: ChatMessageItem = { role: 'user', content: trimmed };
    setLocalMessages((prev) => [...prev, userMessage]);
    setInput('');

    mutation.mutate(
      { data: { message: trimmed }, sessionId },
      {
        onSuccess: (response) => {
          setSessionId(response.session_id);
          const assistantMessage: ChatMessageItem = {
            role: 'assistant',
            content: response.answer,
            sources: response.sources,
            confidence: response.confidence,
          };
          setLocalMessages((prev) => [...prev, assistantMessage]);
        },
        onError: () => {
          toast({
            title: formatMessage({ id: 'chat.error' }),
            status: 'error',
            duration: 3000,
            isClosable: true,
          });
        },
      },
    );
  }, [input, mutation, sessionId, toast, formatMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const isEmpty = localMessages.length === 0 && !isHistoryLoading;

  return (
    <Flex direction="column" h="70vh" borderWidth="1px" borderRadius="lg" overflow="hidden">
      <Box flex="1" overflowY="auto" p={4} ref={scrollAreaRef} onScroll={handleScroll}>
        {isFetchingNextPage && (
          <Flex justify="center" py={2}>
            <Spinner size="sm" />
          </Flex>
        )}
        {isHistoryLoading && (
          <Flex justify="center" align="center" h="full">
            <Spinner />
          </Flex>
        )}
        {isEmpty && (
          <Flex justify="center" align="center" h="full">
            <Text color="gray.500">{formatMessage({ id: 'chat.empty' })}</Text>
          </Flex>
        )}
        <VStack spacing={3} align="stretch">
          {localMessages.map((msg, idx) => (
            <Flex key={idx} justify={msg.role === 'user' ? 'flex-end' : 'flex-start'}>
              <Box
                maxW="75%"
                px={4}
                py={2}
                borderRadius="lg"
                bg={msg.role === 'user' ? 'blue.500' : 'gray.100'}
                color={msg.role === 'user' ? 'white' : 'inherit'}
              >
                <Text whiteSpace="pre-wrap">{msg.content}</Text>
                {msg.role === 'assistant' && msg.confidence != null && (
                  <Badge mt={1} colorScheme="green" fontSize="xs">
                    {formatMessage({ id: 'chat.confidence' })}: {Math.round(msg.confidence * 100)}%
                  </Badge>
                )}
                {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                  <SourcesSection sources={msg.sources} />
                )}
              </Box>
            </Flex>
          ))}
          {mutation.isPending && (
            <Flex justify="flex-start">
              <Box px={4} py={2} borderRadius="lg" bg="gray.100">
                <Spinner size="sm" />
              </Box>
            </Flex>
          )}
          <Box ref={messagesEndRef} />
        </VStack>
      </Box>

      <Flex p={3} borderTopWidth="1px" gap={2}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={formatMessage({ id: 'chat.placeholder' })}
          isDisabled={mutation.isPending}
        />
        <IconButton
          aria-label={formatMessage({ id: 'chat.send' })}
          onClick={handleSend}
          isLoading={mutation.isPending}
          colorScheme="blue"
        >
          {'\u2192'}
        </IconButton>
      </Flex>
    </Flex>
  );
};
