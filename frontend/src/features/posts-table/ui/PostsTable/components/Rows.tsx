import { Td, Tr } from '@chakra-ui/react';
import type { PostsTableRowsProps } from '@features/posts-table/model';

export const PostsTableRows = ({ rows }: PostsTableRowsProps) => (
  <>
    {rows.map((post) => (
      <Tr key={post.id}>
        <Td>{post.id}</Td>
        <Td fontWeight="600">{post.title}</Td>
        <Td color="text.secondary">{post.body.slice(0, 120)}...</Td>
      </Tr>
    ))}
  </>
);
