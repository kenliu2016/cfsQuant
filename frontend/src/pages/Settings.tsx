import React from 'react';
import { Tabs } from 'antd';
import MarketCodesTab from './settings/MarketCodesTab';
import TenantsTab from './settings/TenantsTab';
import TradingAccountsTab from './settings/TradingAccountsTab';

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
  const items = [
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
    {
      key: 'tenants',
      label: '租户管理',
      children: <TenantsTab />,
    },
  ];

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
