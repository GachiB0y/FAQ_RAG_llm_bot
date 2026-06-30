import { useState } from 'react';
import { useIntl } from 'react-intl';
import { Container, Heading, Stack, Text } from '@chakra-ui/react';
import { PostsTable } from '@features/posts-table';
import { POSTS_PAGE_INITIAL, POSTS_PAGE_SIZE_INITIAL } from '@pages/posts/model/constants';

export const PostsPage = () => {
  const { formatMessage } = useIntl();
  const [page, setPage] = useState(POSTS_PAGE_INITIAL);
  const [pageSize, setPageSize] = useState(POSTS_PAGE_SIZE_INITIAL);

  const handlePageSizeChange = (nextSize: number) => {
    setPageSize(nextSize);
    setPage(POSTS_PAGE_INITIAL);
  };

  return (
    <Container maxW="7xl" py={12}>
      <Stack spacing={6}>
        <Stack spacing={2}>
          <Heading size="lg">{formatMessage({ id: 'posts.page.title' })}</Heading>
          <Text color="text.secondary">{formatMessage({ id: 'posts.page.description' })}</Text>
        </Stack>
        <PostsTable
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
        />
      </Stack>
    </Container>
  );
};
