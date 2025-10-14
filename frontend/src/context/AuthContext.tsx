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
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
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
    if (tenantId) {
      loadSession(tenantId);
    }
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
      const response = await client.get('/api/auth/me');
      if (response.data?.user) {
        const refreshedUser: AuthUser = response.data.user;
        persistSession(tenantId, token, refreshedUser);
      }
    } catch (error) {
      // token invalid
      clearSession(tenantId);
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
      void refreshSession();
    }
  }, [token, tenantId, refreshSession]);

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
