import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";
import { message } from "antd";
import type { ApiError } from "../types";

// ── HTTP instance ──

const http: AxiosInstance = axios.create({
  baseURL: "/api",
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// ── Interceptors ──

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const traceId =
    crypto.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  config.headers.set("X-Trace-Id", traceId);
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const detail =
      error.response?.data?.message ??
      error.response?.data?.detail ??
      error.message;
    message.error(`Request failed: ${detail}`);
    return Promise.reject(error);
  },
);

// ── Typed helpers ──

export async function get<T = unknown>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const { data } = await http.get<T>(url, config);
  return data;
}

export async function post<T = unknown>(
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const { data } = await http.post<T>(url, body, config);
  return data;
}

export async function del<T = void>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const { data } = await http.delete<T>(url, config);
  return data;
}

export default http;
