import axios from 'axios'

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

const client = axios.create({ baseURL: apiBaseUrl })
export default client
