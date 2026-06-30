import { POSTS_TOTAL_FALLBACK } from '@entities/post/model/constants';
import type { Post, PostsQueryParams, PostsQueryResult } from '@entities/post/model/types';
import { httpClient } from '@shared/api';

export const fetchPosts = async (params: PostsQueryParams): Promise<PostsQueryResult> => {
  const searchParams = new URLSearchParams({
    _page: params.page.toString(),
    _limit: params.limit.toString(),
  });

  const items = await httpClient.get<Post[]>(`/posts?${searchParams.toString()}`);

  return {
    items,
    total: POSTS_TOTAL_FALLBACK,
  };
};
