import { Card, CardBody, Heading, Text, VStack } from '@chakra-ui/react';
import { type SectionCardProps } from '@pages/home/model/types';

import styles from './HomePage.module.scss';

export const SectionCard = ({
  titleId,
  descriptionId,
  messages,
  formatMessage,
}: SectionCardProps) => (
  <Card bg="whiteAlpha.50" border="1px solid" borderColor="whiteAlpha.200">
    <CardBody>
      <Heading className={styles.sectionTitle} size="md">
        {formatMessage({ id: titleId })}
      </Heading>
      <Text mt={2} color="gray.400">
        {formatMessage({ id: descriptionId })}
      </Text>
      <VStack align="stretch" spacing={2}>
        {messages.map((messageId) => (
          <Text key={messageId} fontSize="sm" color="gray.300">
            - {formatMessage({ id: messageId })}
          </Text>
        ))}
      </VStack>
    </CardBody>
  </Card>
);
