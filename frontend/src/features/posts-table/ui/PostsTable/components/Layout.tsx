import { Card, CardBody, CardHeader, Heading, Stack, Text } from '@chakra-ui/react';
import type { PostsTableLayoutProps } from '@features/posts-table/model';

export const PostsTableLayout = ({ title, subtitle, children }: PostsTableLayoutProps) => (
  <Card bg="bg.surface" border="1px solid" borderColor="border.default">
    <CardHeader>
      <Stack spacing={2}>
        <Heading size="md">{title}</Heading>
        <Text color="text.secondary">{subtitle}</Text>
      </Stack>
    </CardHeader>
    <CardBody>{children}</CardBody>
  </Card>
);
