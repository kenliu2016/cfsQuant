import axios from 'axios';

// 扩展 Vite 默认的 ImportMetaEnv 类型，声明项目中使用到的变量
declare global {
  interface ImportMetaEnv {
    readonly VITE_API_BASE_URL?: string;
  }
}

// 使用相对路径作为API基础URL，这样请求会发送到与前端相同的域名和端口
// 然后通过Nginx反向代理转发到后端服务，避免CORS问题
const client = axios.create({
  baseURL: '', // 空字符串，避免与API路径中的/api重复
  timeout: 60000, // 增加到60秒超时，因为大数据量查询可能需要更长时间
  headers: {
    'Content-Type': 'application/json',
  },
})

client.interceptors.request.use((config) => {
  const tenantId = typeof window !== 'undefined' ? window.localStorage.getItem('cfsTenantId') || 'public' : 'public';
  if (typeof window !== 'undefined') {
    if (tenantId) {
      config.headers = config.headers ?? {};
      config.headers['X-Tenant-ID'] = tenantId;
    }
    const token =
      window.localStorage.getItem(`cfsToken_${tenantId}`) || window.localStorage.getItem('cfsToken_shared');
    if (token) {
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
})

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (typeof window !== 'undefined' && error?.response?.status === 401) {
      console.log('Received 401 error, attempting token refresh...');
      
      const tenantId = window.localStorage.getItem('cfsTenantId') || 'public';
      const originalRequest = error.config;
      
      // 检查是否是刷新令牌的请求本身失败，避免无限循环
      if (originalRequest.url?.includes('/api/auth/refresh')) {
        console.log('Token refresh request failed, clearing session...');
        clearSession(tenantId);
        return Promise.reject(error);
      }
      
      // 检查是否有有效的令牌可以用于刷新
      const token = window.localStorage.getItem(`cfsToken_${tenantId}`) || window.localStorage.getItem('cfsToken_shared');
      if (!token) {
        console.log('No token found, clearing session...');
        clearSession(tenantId);
        return Promise.reject(error);
      }
      
      // 检查是否已经尝试过刷新令牌
      if (!originalRequest._retry) {
        originalRequest._retry = true;
        
        try {
          console.log('Attempting to refresh token...');
          const refreshResponse = await client.post('/api/auth/refresh');
          
          if (refreshResponse.status === 200) {
            const newToken = refreshResponse.data.access_token;
            const user = refreshResponse.data.user;
            
            // 保存新的令牌和用户信息
            window.localStorage.setItem(`cfsToken_${tenantId}`, newToken);
            window.localStorage.setItem(`cfsUser_${tenantId}`, JSON.stringify(user));
            
            // 更新原始请求的Authorization头
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            
            console.log('Token refreshed successfully, retrying original request...');
            return client(originalRequest);
          }
        } catch (refreshError) {
          console.log('Token refresh failed, clearing session...');
          clearSession(tenantId);
        }
      }
      
      // 如果刷新失败或已经重试过，清除会话
      clearSession(tenantId);
    }
    return Promise.reject(error);
  },
)

/**
 * 清除会话数据
 * @param tenantId 租户ID
 */
function clearSession(tenantId: string): void {
  window.localStorage.removeItem(`cfsToken_${tenantId}`);
  window.localStorage.removeItem(`cfsUser_${tenantId}`);
  window.localStorage.removeItem('cfsToken_shared');
  window.localStorage.removeItem('cfsUser_shared');
  window.dispatchEvent(new CustomEvent('auth:logout', { detail: { tenantId } }));
}

export default client

// 为了支持查询参数，确保类型声明与axios库保持一致
declare module 'axios' {
  interface AxiosRequestConfig {
    params?: any;
  }
}
