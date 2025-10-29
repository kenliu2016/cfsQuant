import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import client from '../api/client';
import { useTenant } from './TenantContext';

interface AuthUser {
  id: string;
  tenant_id: string;
  email: string;
  full_name?: string;
  is_admin?: boolean;
  is_super_admin?: boolean;
}

interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (tenantId: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshSession: () => Promise<void>;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const tokenKey = (tenantId: string) => `cfsToken_${tenantId}`;
const userKey = (tenantId: string) => `cfsUser_${tenantId}`;
const SHARED_TOKEN_KEY = 'cfsToken_shared';
const SHARED_USER_KEY = 'cfsUser_shared';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tenantId, setTenantId, refreshTenants } = useTenant();
  
  // 同步初始化认证状态，避免异步加载导致的认证检查时机问题
  const initialTenantId = tenantId || 'public';
  const initialToken = window.localStorage.getItem(tokenKey(initialTenantId)) || window.localStorage.getItem(SHARED_TOKEN_KEY);
  const initialUser = window.localStorage.getItem(userKey(initialTenantId)) || window.localStorage.getItem(SHARED_USER_KEY);
  
  const [token, setToken] = useState<string | null>(initialToken);
  const [user, setUser] = useState<AuthUser | null>(initialUser ? JSON.parse(initialUser) as AuthUser : null);
  const [loading, setLoading] = useState<boolean>(false);

  const loadSession = useCallback(
    (tenant: string) => {
      const storedToken =
        window.localStorage.getItem(tokenKey(tenant)) || window.localStorage.getItem(SHARED_TOKEN_KEY);
      const storedUser =
        window.localStorage.getItem(userKey(tenant)) || window.localStorage.getItem(SHARED_USER_KEY);
      setToken(storedToken);
      setUser(storedUser ? (JSON.parse(storedUser) as AuthUser) : null);
    },
    [],
  );

  useEffect(() => {
    // 应用启动时尝试加载会话，无论tenantId是否存在
    const currentTenantId = tenantId || 'public';
    loadSession(currentTenantId);
  }, [tenantId, loadSession]);

  const persistSession = useCallback((tenant: string, newToken: string, newUser: AuthUser) => {
    window.localStorage.setItem(tokenKey(tenant), newToken);
    window.localStorage.setItem(userKey(tenant), JSON.stringify(newUser));
    window.localStorage.setItem(SHARED_TOKEN_KEY, newToken);
    window.localStorage.setItem(SHARED_USER_KEY, JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  }, []);

  const clearSession = useCallback(
    (tenant: string) => {
      window.localStorage.removeItem(tokenKey(tenant));
      window.localStorage.removeItem(userKey(tenant));
      if (tenant === tenantId) {
        setToken(null);
        setUser(null);
        window.localStorage.removeItem(SHARED_TOKEN_KEY);
        window.localStorage.removeItem(SHARED_USER_KEY);
      }
    },
    [tenantId],
  );

  const login = useCallback(
    async (tenant: string, email: string, password: string) => {
      setLoading(true);
      try {
        const response = await client.post('/api/auth/login', {
          tenant_id: tenant,
          email,
          password,
        });
        const accessToken: string = response.data?.access_token;
        const authUser: AuthUser = response.data?.user;
        if (!accessToken || !authUser) {
          throw new Error('登录失败');
        }
        setTenantId(tenant);
        persistSession(tenant, accessToken, authUser);
        await refreshTenants();
      } finally {
        setLoading(false);
      }
    },
    [persistSession, setTenantId, refreshTenants],
  );

  const logout = useCallback(() => {
    const tenant = tenantId || 'public';
    clearSession(tenant);
    setTenantId('public');
  }, [clearSession, tenantId, setTenantId]);

  const refreshSession = useCallback(async () => {
    if (!token || !tenantId) return;
    try {
      // 首先尝试刷新令牌
      const refreshResponse = await client.post('/api/auth/refresh');
      if (refreshResponse.status === 200) {
        const newToken: string = refreshResponse.data?.access_token;
        const refreshedUser: AuthUser = refreshResponse.data?.user;
        if (newToken && refreshedUser) {
          persistSession(tenantId, newToken, refreshedUser);
          console.log('Token refreshed successfully');
          return;
        }
      }
    } catch (refreshError) {
      console.log('Token refresh failed, attempting to validate current token...');
      // 如果刷新失败，尝试使用当前令牌验证用户信息
      try {
        const response = await client.get('/api/auth/me');
        if (response.data?.user) {
          const refreshedUser: AuthUser = response.data.user;
          persistSession(tenantId, token, refreshedUser);
          console.log('Current token is still valid');
          return;
        }
      } catch (meError) {
        console.log('Current token is invalid, clearing session...');
        clearSession(tenantId);
      }
    }
  }, [token, tenantId, persistSession, clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token),
      login,
      logout,
      refreshSession,
      loading,
    }),
    [token, user, login, logout, refreshSession, loading],
  );

  useEffect(() => {
    if (token && tenantId) {
      // 使用更稳定的防抖机制，避免频繁调用refresh接口
      const timer = setTimeout(() => {
        void refreshSession();
      }, 30000); // 30秒延迟，大幅减少刷新频率
      
      return () => clearTimeout(timer);
    }
  }, [token, tenantId]);

  useEffect(() => {
    const handler = (event: Event) => {
      const custom = event as CustomEvent<{ tenantId?: string }>;
      const targetTenant = custom.detail?.tenantId;
      const currentTenant = tenantId || 'public';
      if (!targetTenant || targetTenant === currentTenant) {
        clearSession(currentTenant);
        setTenantId('public');
      }
    };
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, [clearSession, tenantId, setTenantId]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
