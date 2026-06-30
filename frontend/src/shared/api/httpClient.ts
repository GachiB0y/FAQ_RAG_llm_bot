import { AppError } from '@shared/api/model/errors';
import type {
  ApiErrorPayload,
  BaseHttpClientConfig,
  RetryableRequestConfig,
  TokenPair,
} from '@shared/api/model/types';
import axios, {
  type AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosRequestHeaders,
} from 'axios';

const DEFAULT_API_URL = import.meta.env.VITE_API_URL ?? '/api';

export class BaseHttpClient {
  protected readonly instance: AxiosInstance;

  private tokens?: TokenPair;
  private refreshInFlight?: Promise<TokenPair | null>;
  private readonly refreshClient: AxiosInstance;
  private readonly config: BaseHttpClientConfig;

  constructor(config: BaseHttpClientConfig = {}) {
    this.config = config;
    this.instance = axios.create({
      baseURL: config.baseURL ?? DEFAULT_API_URL,
      timeout: config.timeout ?? 15_000,
      withCredentials: config.withCredentials ?? true,
    });

    this.refreshClient = axios.create({
      baseURL: this.instance.defaults.baseURL,
      timeout: config.timeout ?? 15_000,
      withCredentials: config.withCredentials ?? true,
    });

    this.attachInterceptors();
  }

  setTokens(nextTokens: TokenPair | undefined): void {
    this.tokens = nextTokens;
  }

  clearTokens(): void {
    this.tokens = undefined;
  }

  getTokens(): TokenPair | undefined {
    return this.tokens;
  }

  async get<TResponse>(url: string, config?: AxiosRequestConfig): Promise<TResponse> {
    return this.request<TResponse>({ ...config, url, method: 'get' });
  }

  async post<TResponse, TPayload = unknown>(
    url: string,
    data?: TPayload,
    config?: AxiosRequestConfig,
  ): Promise<TResponse> {
    return this.request<TResponse>({
      ...config,
      url,
      method: 'post',
      data,
    });
  }

  async put<TResponse, TPayload = unknown>(
    url: string,
    data?: TPayload,
    config?: AxiosRequestConfig,
  ): Promise<TResponse> {
    return this.request<TResponse>({
      ...config,
      url,
      method: 'put',
      data,
    });
  }

  async patch<TResponse, TPayload = unknown>(
    url: string,
    data?: TPayload,
    config?: AxiosRequestConfig,
  ): Promise<TResponse> {
    return this.request<TResponse>({
      ...config,
      url,
      method: 'patch',
      data,
    });
  }

  async delete<TResponse>(url: string, config?: AxiosRequestConfig): Promise<TResponse> {
    return this.request<TResponse>({ ...config, url, method: 'delete' });
  }

  protected async request<TResponse>(config: AxiosRequestConfig): Promise<TResponse> {
    const response = await this.instance.request<TResponse>(config);
    return response.data;
  }

  private attachInterceptors(): void {
    this.instance.interceptors.request.use((request) => {
      if (this.tokens?.accessToken) {
        const headers = AxiosHeaders.from(request.headers);
        headers.set('Authorization', `Bearer ${this.tokens.accessToken}`);
        request.headers = headers;
      }

      return request;
    });

    this.instance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ApiErrorPayload>) => {
        const originalRequest = error.config as RetryableRequestConfig | undefined;
        const shouldRetry =
          !!originalRequest &&
          !originalRequest._retry &&
          error.response?.status === 401 &&
          this.tokens?.refreshToken &&
          this.config.refreshEndpoint;

        if (shouldRetry) {
          originalRequest._retry = true;
          const newTokens = await this.performRefresh();

          if (newTokens) {
            const headers = AxiosHeaders.from(
              originalRequest.headers as AxiosRequestHeaders | AxiosHeaders | undefined,
            );
            headers.set('Authorization', `Bearer ${newTokens.accessToken}`);
            originalRequest.headers = headers;
          }

          return this.instance.request(originalRequest);
        }

        return Promise.reject(this.normalizeError(error));
      },
    );
  }

  private async performRefresh(): Promise<TokenPair | null> {
    if (this.refreshInFlight) {
      return this.refreshInFlight;
    }

    if (!this.tokens?.refreshToken || !this.config.refreshEndpoint) {
      this.clearTokens();
      return null;
    }

    this.refreshInFlight = this.refreshClient
      .post<TokenPair>(this.config.refreshEndpoint, {
        refresh_token: this.tokens.refreshToken,
      })
      .then((response) => {
        this.setTokens(response.data);
        return response.data;
      })
      .catch((refreshError: AxiosError<ApiErrorPayload>) => {
        this.clearTokens();
        throw this.normalizeError(refreshError);
      })
      .finally(() => {
        this.refreshInFlight = undefined;
      });

    return this.refreshInFlight;
  }

  private normalizeError(error: AxiosError<ApiErrorPayload>): AppError {
    const status = error.response?.status;
    const payload = error.response?.data;
    const message =
      payload?.message ||
      error.message ||
      'Произошла ошибка при выполнении запроса. Попробуйте повторить позже.';

    return new AppError(message, payload?.code, status, payload?.details ?? payload?.errors);
  }
}

export const httpClient = new BaseHttpClient({
  baseURL: DEFAULT_API_URL,
  refreshEndpoint: '/auth/refresh',
});
