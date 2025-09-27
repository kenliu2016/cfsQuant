import axios from 'axios';

// 添加TypeScript类型定义以解决ImportMeta.env类型错误
declare global {
  interface ImportMeta {
    env: {
      VITE_API_BASE_URL?: string;
    };
  }
}

// 从环境变量中获取后端API地址，如果没有则使用默认值
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// 创建axios实例
const client = axios.create({
  baseURL: apiBaseUrl,
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
