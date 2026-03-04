import type { ChatHistoryResponse,ChatRequest } from '@shared/api';
import { chatApi } from '@shared/api';
import { useInfiniteQuery,useMutation } from '@tanstack/react-query';

const CHAT_PAGE_SIZE = 50;

export const useSendMessage = () => {
  return useMutation({
    mutationFn: ({ data, sessionId }: { data: ChatRequest; sessionId?: string }) =>
      chatApi.send(data, sessionId),
  });
};

export const useChatHistory = () => {
  return useInfiniteQuery<ChatHistoryResponse>({
    queryKey: ['chat', 'history'],
    queryFn: ({ pageParam }) =>
      chatApi.getHistory({
        limit: CHAT_PAGE_SIZE,
        offset: pageParam as number,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    staleTime: 0,
  });
};
