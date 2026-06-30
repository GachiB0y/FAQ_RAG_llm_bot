import { Box, Text } from '@chakra-ui/react';
import type { PostsTableEmptyProps } from '@features/posts-table/model';

export const PostsTableEmpty = ({ text }: PostsTableEmptyProps) => (
  <Box py={10} textAlign="center">
    <Text color="text.secondary">{text}</Text>
  </Box>
);
