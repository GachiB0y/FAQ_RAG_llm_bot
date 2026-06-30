import type { AxiosRequestConfig } from 'axios';

export type TokenPair = {
  accessToken: string;
  refreshToken?: string;
};

export type ApiErrorPayload = {
  message?: string;
  code?: string;
  details?: Record<string, unknown>;
  errors?: Record<string, string[]>;
};

export type BaseHttpClientConfig = {
  baseURL?: string;
  timeout?: number;
  withCredentials?: boolean;
  refreshEndpoint?: string;
};

export type RetryableRequestConfig = AxiosRequestConfig & { _retry?: boolean };
