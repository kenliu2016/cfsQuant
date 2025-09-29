import axios from 'axios';

// 添加TypeScript类型定义以解决ImportMeta.env类型错误
declare global {
  interface ImportMeta {
    env: {
      VITE_API_BASE_URL?: string;
    };
  }
}

// 使用相对路径作为API基础URL，这样请求会发送到与前端相同的域名和端口
// 然后通过Nginx反向代理转发到后端服务，避免CORS问题
const client = axios.create({
  baseURL: '/api',
  timeout: 30000, // 增加超时时间，因为大数据量查询可能需要更长时间
  headers: {
    'Content-Type': 'application/json',
  },
})

export default client

// 为了支持查询参数，确保类型声明与axios库保持一致
declare module 'axios' {
  interface AxiosRequestConfig {
    params?: any;
  }
}
