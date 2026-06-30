export type PostsTableColumn = {
  id: 'id' | 'title' | 'preview';
  titleIntlKey: string;
  width?: string | number;
};

export const POSTS_TABLE_COLUMNS: PostsTableColumn[] = [
  { id: 'id', titleIntlKey: 'posts.table.column.id', width: '80px' },
  { id: 'title', titleIntlKey: 'posts.table.column.title' },
  { id: 'preview', titleIntlKey: 'posts.table.column.preview' },
];
