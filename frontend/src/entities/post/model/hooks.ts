import { fetchPosts } from '@entities/post/api/postApi';
import { useQuery } from '@tanstack/react-query';

import type { PostsQueryParams, PostsQueryResult } from './types';

const postsQueryKeys = {
  all: ['posts'] as const,
  list: (page: number, limit: number) => [...postsQueryKeys.all, page, limit] as const,
};

export const usePostsQuery = (params: PostsQueryParams) =>
  useQuery<PostsQueryResult>({
    queryKey: postsQueryKeys.list(params.page, params.limit),
    queryFn: () => fetchPosts(params),
    staleTime: 60_000,
  });
