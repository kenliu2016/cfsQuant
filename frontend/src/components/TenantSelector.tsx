import React from 'react';
import { Select, Space, Button, Tooltip } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useTenant } from '../context/TenantContext';

const TenantSelector: React.FC = () => {
  const { tenantId, tenants, setTenantId, refreshTenants } = useTenant();

  const options = tenants.map((tenant) => ({
    label: tenant.name || tenant.tenant_id,
    value: tenant.tenant_id,
    disabled: tenant.is_active === false,
  }));

  return (
    <Space>
      <Select
        value={tenantId}
        onChange={setTenantId}
        options={options}
        style={{ minWidth: 200 }}
        placeholder="选择租户"
      />
      <Tooltip title="刷新租户列表">
        <Button icon={<ReloadOutlined />} onClick={() => refreshTenants()} />
      </Tooltip>
    </Space>
  );
};

export default TenantSelector;
