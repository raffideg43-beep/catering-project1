import axios, { AxiosInstance } from "axios";

let apiClient: AxiosInstance | null = null;

export function getApiClient(): AxiosInstance {
  if (!apiClient) {
    apiClient = axios.create({
      baseURL: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
      timeout: 30_000,
    });

    // Request interceptor: attach JWT token
    apiClient.interceptors.request.use(
      (config) => {
        const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor: handle error codes
    apiClient.interceptors.response.use(
      (response) => response,
      (error) => {
        const status = error.response?.status;

        if (status === 401) {
          if (typeof window !== "undefined") {
            localStorage.removeItem("auth_token");
            window.location.href = "/login";
          }
        } else if (status === 429) {
          // Rate limit — tampilkan toast jika ada
          if (typeof window !== "undefined") {
            const event = new CustomEvent("app:toast", {
              detail: { message: "⚠️ Terlalu banyak request. Tunggu sebentar.", type: "warning" },
            });
            window.dispatchEvent(event);
          }
        } else if (status && status >= 500) {
          if (typeof window !== "undefined") {
            const event = new CustomEvent("app:toast", {
              detail: { message: "❌ Server sedang bermasalah. Coba lagi.", type: "error" },
            });
            window.dispatchEvent(event);
          }
        }

        return Promise.reject(error);
      }
    );

  }

  return apiClient;
}

export async function apiGet(endpoint: string, params?: any) {
  const client = getApiClient();
  const response = await client.get(endpoint, { params });
  return response.data;
}

export async function apiPost(endpoint: string, data?: any) {
  const client = getApiClient();
  const response = await client.post(endpoint, data);
  return response.data;
}

export async function apiPut(endpoint: string, data?: any) {
  const client = getApiClient();
  const response = await client.put(endpoint, data);
  return response.data;
}

export async function apiDelete(endpoint: string) {
  const client = getApiClient();
  const response = await client.delete(endpoint);
  return response.data;
}

export async function apiPatch(endpoint: string, data?: any) {
  const client = getApiClient();
  const response = await client.patch(endpoint, data);
  return response.data;
}

