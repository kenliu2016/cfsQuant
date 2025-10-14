import React, { useMemo } from 'react';
import { Tabs } from 'antd';
import MarketCodesTab from './settings/MarketCodesTab';
import TenantsTab from './settings/TenantsTab';
import TradingAccountsTab from './settings/TradingAccountsTab';
import TenantUsersTab from './settings/TenantUsersTab';
import { useAuth } from '../context/AuthContext';

const tabStyle = {
  color: '#FFFFFF',
  '& .ant-tabs-tab': {
    color: '#FFFFFF !important',
  },
  '& .ant-tabs-tab-btn': {
    color: '#FFFFFF !important',
  },
  '& .ant-tabs-nav::before': {
    borderBottom: '1px solid #333333 !important',
  },
  '& .ant-tabs-ink-bar': {
    background: '#1890ff !important',
  },
};

const Settings: React.FC = () => {
  const { user } = useAuth();
  const items = useMemo(() => {
    const list = [
      {
        key: 'market',
        label: '交易对',
        children: <MarketCodesTab />,
      },
      {
        key: 'trading',
        label: '交易账户',
        children: <TradingAccountsTab />,
      },
    ];
    if (user?.is_admin || user?.is_super_admin) {
      list.push({ key: 'users', label: '租户用户', children: <TenantUsersTab /> });
    }
    if (user?.is_super_admin) {
      list.push({ key: 'tenants', label: '租户管理', children: <TenantsTab /> });
    }
    return list;
  }, [user]);

  return (
    <div style={{ padding: '0px 0px 0px 0px' }}>
      <Tabs 
        items={items} 
        destroyInactiveTabPane
        style={tabStyle}
        className="custom-tabs"
      />
    </div>
  );
};

export default Settings;
