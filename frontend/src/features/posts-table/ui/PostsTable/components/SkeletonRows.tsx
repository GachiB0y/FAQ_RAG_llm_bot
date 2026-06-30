import { Skeleton, Td, Tr } from '@chakra-ui/react';
import type { PostsTableSkeletonRowsProps } from '@features/posts-table/model';

export const PostsTableSkeletonRows = ({ columns, rowsCount }: PostsTableSkeletonRowsProps) => (
  <>
    {Array.from({ length: rowsCount }).map((_, index) => (
      <Tr key={`skeleton-${index}`}>
        {columns.map((column) => (
          <Td key={`${column.id}-${index}`}>
            <Skeleton height="16px" />
          </Td>
        ))}
      </Tr>
    ))}
  </>
);
