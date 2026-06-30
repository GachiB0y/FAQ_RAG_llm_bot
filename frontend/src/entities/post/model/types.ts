export type Post = {
  userId: number;
  id: number;
  title: string;
  body: string;
};

export type PostsQueryParams = {
  page: number;
  limit: number;
};

export type PostsQueryResult = {
  items: Post[];
  total: number;
};
