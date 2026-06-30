import { settingsApi } from '@shared/api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { SystemSettings } from './types';

const QUERY_KEY = ['settings'];

export const useSettings = () => {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: settingsApi.get,
  });
};

export const useUpdateSettings = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<SystemSettings>) => settingsApi.update(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
};
