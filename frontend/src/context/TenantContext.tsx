import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import client from '../api/client';

export interface TenantRecord {
  tenant_id: string;
  name: string;
  description?: string;
  is_active?: boolean;
}

interface TenantContextValue {
  tenantId: string;
  tenants: TenantRecord[];
  setTenantId: (tenantId: string) => void;
  refreshTenants: () => Promise<void>;
}

const TenantContext = createContext<TenantContextValue | undefined>(undefined);

const TENANT_STORAGE_KEY = 'cfsTenantId';

export const TenantProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [tenantId, setTenantIdState] = useState<string>(() => {
    const stored = window.localStorage.getItem(TENANT_STORAGE_KEY);
    return stored || 'public';
  });
  const [tenants, setTenants] = useState<TenantRecord[]>([]);

  const fetchTenants = useCallback(async () => {
    const token = window.localStorage.getItem(`cfsToken_${tenantId}`);
    if (!token) {
      setTenants([]);
      return;
    }
    try {
      const response = await client.get('/api/tenants', {
        params: { active: null },
      });
      const rows: TenantRecord[] = response.data?.rows || [];
      setTenants(rows);
      if (rows.length > 0) {
        const exists = rows.some((tenant) => tenant.tenant_id === tenantId);
        if (!exists) {
          const fallback = rows.find((tenant) => tenant.tenant_id === 'public') || rows[0];
          setTenantIdState(fallback.tenant_id);
          window.localStorage.setItem(TENANT_STORAGE_KEY, fallback.tenant_id);
        }
      }
    } catch (error) {
      console.error('Failed to load tenants', error);
      setTenants([
        {
          tenant_id: tenantId,
          name: tenantId,
          is_active: true,
        },
      ]);
    }
  }, [tenantId]);

  useEffect(() => {
    void fetchTenants();
  }, [fetchTenants]);

  const setTenantId = useCallback((id: string) => {
    setTenantIdState(id);
    window.localStorage.setItem(TENANT_STORAGE_KEY, id);
  }, []);

  const value = useMemo(
    () => ({ tenantId, tenants, setTenantId, refreshTenants: fetchTenants }),
    [tenantId, tenants, setTenantId, fetchTenants],
  );

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
};

export const useTenant = (): TenantContextValue => {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error('useTenant must be used within TenantProvider');
  }
  return ctx;
};
