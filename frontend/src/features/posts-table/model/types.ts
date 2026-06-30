import type { ReactNode } from 'react';
import type { Post } from '@entities/post';
import type { PostsTableColumn } from '@features/posts-table/model/constants';

export type PostsTableProps = {
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
};

export type PostsTableLayoutProps = {
  title: string;
  subtitle: string;
  children: ReactNode;
};

export type PostsTableErrorProps = {
  title: string;
  description: string;
  actionLabel: string;
  onRetry: () => void;
  isLoading: boolean;
};

export type PostsTableHeadProps = {
  columns: PostsTableColumn[];
  renderTitle: (id: string) => string;
};

export type PostsTableSkeletonRowsProps = {
  columns: PostsTableColumn[];
  rowsCount: number;
};

export type PostsTableRowsProps = {
  rows: Post[];
};

export type PostsTableEmptyProps = {
  text: string;
};

export type PostsTablePaginationProps = {
  page: number;
  totalPages: number;
  pageSize: number;
  pageSizeOptions: number[];
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  infoText: string;
  rowsPerPageLabel: string;
  prevLabel: string;
  nextLabel: string;
};
