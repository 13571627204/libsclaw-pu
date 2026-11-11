import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

const AUTH_HEADER = 'Authorization';
const LOCALE_HEADER = 'Accept-Language';

let configured = false;
let originalFetch: typeof window.fetch | null = null;

export const httpClient = axios;
export const apiV1Client = axios.create({ baseURL: '/api/v1' });

function getToken(): string | null {
  return localStorage.getItem('token');
}

function getLocale(): string | null {
  return localStorage.getItem('astrbot-locale');
}

function setAxiosHeader(
  headers: InternalAxiosRequestConfig['headers'],
  key: string,
  value: string,
) {
  if (typeof headers.set === 'function') {
    headers.set(key, value);
    return;
  }
  headers[key] = value;
}

function attachAxiosHeaders(config: InternalAxiosRequestConfig) {
  const token = getToken();
  if (token) {
    setAxiosHeader(config.headers, AUTH_HEADER, `Bearer ${token}`);
  }

  const locale = getLocale();
  if (locale) {
    setAxiosHeader(config.headers, LOCALE_HEADER, locale);
  }

  return config;
}

function normalizeAxiosError(error: AxiosError) {
  if (error.response?.status === 401) {
    let requestPath = '';
    try {
      const url = error.config?.url || '';
      const baseURL = error.config?.baseURL;
      const resolvedUrl =
        url && baseURL && !/^([a-z][a-z\d+\-.]*:)?\/\//i.test(url)
          ? `${baseURL.replace(/\/+$/, '')}/${url.replace(/^\/+/, '')}`
          : url;
      const requestUrl = new URL(resolvedUrl || '/', window.location.origin);
      if (requestUrl.origin === window.location.origin) {
        requestPath = requestUrl.pathname;
      }
    } catch {
      requestPath = '';
    }

    const isAuthChallenge =
      [
        '/api/auth/login',
        '/api/auth/setup',
        '/api/auth/setup-status',
        '/api/v1/auth/login',
        '/api/v1/auth/setup',
        '/api/v1/auth/setup-status',
      ].includes(requestPath) ||
      Boolean(
        (
          error.response.data as
            | { data?: { totp_required?: boolean } }
            | undefined
        )?.data?.totp_required,
      );

    if (requestPath.startsWith('/api/') && !isAuthChallenge) {
      [
        'user',
        'token',
        'change_pwd_hint',
        'md5_pwd_hint',
        'password_upgrade_required',
      ].forEach((key) => localStorage.removeItem(key));

      if (!window.location.hash.startsWith('#/auth/login')) {
        window.location.hash = '/auth/login';
      }
    }
  }

  if (error.response?.status === 429) {
    const data = error.response.data as { message?: string } | undefined;
    if (data?.message) {
      return Promise.reject(data.message);
    }
  }
  if (error.response?.status === 405) {
    // 前端已更新但后端进程仍是旧版本，新接口尚未注册
    return Promise.reject(`后端未加载该接口（${error.config?.url || ''}），请重启后端服务后重试`);
  }
  return Promise.reject(error);
}

const BACKEND_RETRY_LIMIT = 90;
const BACKEND_RETRY_DELAY_MS = 1000;

const NETWORK_RETRY_LIMIT = 4;
const IDEMPOTENT_METHODS = ['get', 'head', 'options'];

type RetryableConfig = InternalAxiosRequestConfig & {
  __backendRetry?: number;
  __networkRetry?: number;
};

// The dev proxy marks "backend not reachable yet" responses; wait and retry
// instead of surfacing them as errors while the Python backend boots.
export function isBackendUnavailable(status: number, headers: { get?: (k: string) => unknown } | Record<string, unknown> | undefined) {
  if (status !== 503 || !headers) return false;
  const value =
    typeof (headers as { get?: unknown }).get === 'function'
      ? (headers as { get: (k: string) => unknown }).get('x-backend-unavailable')
      : (headers as Record<string, unknown>)['x-backend-unavailable'];
  return String(value ?? '') === '1';
}

function installAxiosInterceptors(instance: AxiosInstance) {
  instance.interceptors.request.use(attachAxiosHeaders);
  instance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const config = error.config as RetryableConfig | undefined;
      if (
        config &&
        error.response &&
        isBackendUnavailable(error.response.status, error.response.headers as Record<string, unknown>) &&
        (config.__backendRetry ?? 0) < BACKEND_RETRY_LIMIT
      ) {
        config.__backendRetry = (config.__backendRetry ?? 0) + 1;
        await new Promise((resolve) => setTimeout(resolve, BACKEND_RETRY_DELAY_MS));
        return instance.request(config);
      }
      // 连接被中断（后端重启、代理/网络抖动）且没有任何响应：幂等请求自动退避重试
      if (
        config &&
        !error.response &&
        error.code === 'ERR_NETWORK' &&
        IDEMPOTENT_METHODS.includes((config.method || 'get').toLowerCase()) &&
        (config.__networkRetry ?? 0) < NETWORK_RETRY_LIMIT
      ) {
        config.__networkRetry = (config.__networkRetry ?? 0) + 1;
        await new Promise((resolve) =>
          setTimeout(resolve, BACKEND_RETRY_DELAY_MS * 2 ** (config.__networkRetry! - 1)),
        );
        return instance.request(config);
      }
      return normalizeAxiosError(error);
    },
  );
}

export function fetchWithAuth(input: RequestInfo | URL, init?: RequestInit) {
  const fetchImpl = originalFetch ?? window.fetch.bind(window);
  const token = getToken();
  const locale = getLocale();

  if (!token && !locale) {
    return fetchImpl(input, init);
  }

  const requestHeaders =
    typeof input !== 'string' && 'headers' in input
      ? (input as Request).headers
      : undefined;
  const headers = new Headers(init?.headers || requestHeaders);

  if (token && !headers.has(AUTH_HEADER)) {
    headers.set(AUTH_HEADER, `Bearer ${token}`);
  }
  if (locale && !headers.has(LOCALE_HEADER)) {
    headers.set(LOCALE_HEADER, locale);
  }

  return fetchImpl(input, { ...init, headers });
}

export function setupHttpClient() {
  if (configured) {
    return;
  }

  installAxiosInterceptors(axios);
  installAxiosInterceptors(apiV1Client);

  originalFetch = window.fetch.bind(window);
  window.fetch = fetchWithAuth;

  configured = true;
}
