import { useAuthStore } from '@/stores/auth-store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

class ApiClient {
  private async getHeaders(skipAuth = false): Promise<HeadersInit> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (!skipAuth) {
      const accessToken = useAuthStore.getState().accessToken;
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }
    }

    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'An error occurred' }));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async get<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const headers = await this.getHeaders(options.skipAuth);
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      method: 'GET',
      headers: { ...headers, ...options.headers },
    });

    return this.handleResponse<T>(response);
  }

  async post<T>(endpoint: string, data?: any, options: RequestOptions = {}): Promise<T> {
    const headers = await this.getHeaders(options.skipAuth);
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      method: 'POST',
      headers: { ...headers, ...options.headers },
      body: data ? JSON.stringify(data) : undefined,
    });

    return this.handleResponse<T>(response);
  }

  async put<T>(endpoint: string, data: any, options: RequestOptions = {}): Promise<T> {
    const headers = await this.getHeaders(options.skipAuth);
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      method: 'PUT',
      headers: { ...headers, ...options.headers },
      body: JSON.stringify(data),
    });

    return this.handleResponse<T>(response);
  }

  async delete<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const headers = await this.getHeaders(options.skipAuth);
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      method: 'DELETE',
      headers: { ...headers, ...options.headers },
    });

    return this.handleResponse<T>(response);
  }
}

export const apiClient = new ApiClient(); 