import { useMemo } from 'react';
import { useIntl } from 'react-intl';
import { Divider, Table, TableContainer, Tbody } from '@chakra-ui/react';
import { POSTS_PAGE_SIZES, usePostsQuery } from '@entities/post';
import { POSTS_TABLE_COLUMNS, type PostsTableProps } from '@features/posts-table';

import {
  PostsTableEmpty,
  PostsTableError,
  PostsTableHead,
  PostsTableLayout,
  PostsTablePagination,
  PostsTableRows,
  PostsTableSkeletonRows,
} from './components';

export const PostsTable = ({ page, pageSize, onPageChange, onPageSizeChange }: PostsTableProps) => {
  const { formatMessage } = useIntl();

  const { data, isLoading, isFetching, isError, refetch } = usePostsQuery({
    page,
    limit: pageSize,
  });

  const totalItems = data?.total ?? 0;
  const totalPages = useMemo(
    () => (totalItems > 0 ? Math.ceil(totalItems / pageSize) : 0),
    [totalItems, pageSize],
  );

  const rows = data?.items ?? [];
  const hasRows = rows.length > 0;

  if (isError) {
    return (
      <PostsTableError
        title={formatMessage({ id: 'posts.table.error.title' })}
        description={formatMessage({ id: 'posts.table.error.description' })}
        actionLabel={formatMessage({ id: 'posts.table.action.retry' })}
        onRetry={() => refetch()}
        isLoading={isFetching}
      />
    );
  }

  const paginationText =
    totalPages > 0
      ? formatMessage({ id: 'posts.table.pagination.info' }, { current: page, total: totalPages })
      : formatMessage({ id: 'posts.table.pagination.empty' });

  return (
    <PostsTableLayout
      title={formatMessage({ id: 'posts.table.title' })}
      subtitle={formatMessage({ id: 'posts.table.subtitle' })}
    >
      <TableContainer>
        <Table variant="simple">
          <PostsTableHead
            columns={POSTS_TABLE_COLUMNS}
            renderTitle={(key) => formatMessage({ id: key })}
          />
          <Tbody>
            {isLoading ? (
              <PostsTableSkeletonRows columns={POSTS_TABLE_COLUMNS} rowsCount={pageSize} />
            ) : (
              <PostsTableRows rows={rows} />
            )}
          </Tbody>
        </Table>
      </TableContainer>
      {!isLoading && !hasRows ? (
        <PostsTableEmpty text={formatMessage({ id: 'posts.table.empty' })} />
      ) : null}
      <Divider my={6} borderColor="border.default" />
      <PostsTablePagination
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        pageSizeOptions={POSTS_PAGE_SIZES}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
        infoText={paginationText}
        rowsPerPageLabel={formatMessage({ id: 'posts.table.rowsPerPage' })}
        prevLabel={formatMessage({ id: 'posts.table.pagination.prev' })}
        nextLabel={formatMessage({ id: 'posts.table.pagination.next' })}
      />
    </PostsTableLayout>
  );
};
