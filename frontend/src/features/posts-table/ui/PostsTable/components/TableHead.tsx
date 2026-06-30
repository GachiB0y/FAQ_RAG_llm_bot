import { Th, Thead, Tr } from '@chakra-ui/react';
import type { PostsTableHeadProps } from '@features/posts-table/model';

export const PostsTableHead = ({ columns, renderTitle }: PostsTableHeadProps) => (
  <Thead>
    <Tr>
      {columns.map((column) => (
        <Th key={column.id} w={column.width}>
          {renderTitle(column.titleIntlKey)}
        </Th>
      ))}
    </Tr>
  </Thead>
);
