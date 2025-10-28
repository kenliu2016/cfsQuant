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
  (error) => {
    if (typeof window !== 'undefined' && error?.response?.status === 401) {
      const tenantId = window.localStorage.getItem('cfsTenantId') || 'public';
      window.localStorage.removeItem(`cfsToken_${tenantId}`);
      window.localStorage.removeItem(`cfsUser_${tenantId}`);
      window.localStorage.removeItem('cfsToken_shared');
      window.localStorage.removeItem('cfsUser_shared');
      window.dispatchEvent(new CustomEvent('auth:logout', { detail: { tenantId } }));
    }
    return Promise.reject(error);
  },
)

export default client

// 为了支持查询参数，确保类型声明与axios库保持一致
declare module 'axios' {
  interface AxiosRequestConfig {
    params?: any;
  }
}
