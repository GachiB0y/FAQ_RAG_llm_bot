import { useIntl } from 'react-intl';
import { Container, Heading } from '@chakra-ui/react';
import { ChatWidget } from '@features/chat';

export const ChatPage = () => {
  const { formatMessage } = useIntl();
  return (
    <Container maxW="container.lg" py={6}>
      <Heading size="lg" mb={6}>
        {formatMessage({ id: 'chat.title' })}
      </Heading>
      <ChatWidget />
    </Container>
  );
};
