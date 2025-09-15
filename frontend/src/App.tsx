import React, { useState } from 'react';
import { Layout, Menu, Button } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { Routes, Route, useNavigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Strategy from './pages/Strategy';
import Tuning from './pages/Tuning';
import Monitor from './pages/Monitor';
import Reports from './pages/Reports';
import Progress from './pages/Progress';

const { Sider, Content } = Layout;

const App: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();

  const toggleCollapsed = () => {
    setCollapsed(!collapsed);
  };

  const menuItems = [
    {
      key: 'dashboard',
      label: 'Dashboard',
      onClick: () => navigate('/dashboard'),
    },
    {
      key: 'strategy',
      label: 'Strategy',
      onClick: () => navigate('/strategy'),
    },
    {
      key: 'tuning',
      label: 'Tuning',
      onClick: () => navigate('/tuning'),
    },
    {
      key: 'monitor',
      label: 'Monitor',
      onClick: () => navigate('/monitor'),
    },
    {
      key: 'reports',
      label: 'Reports',
      onClick: () => navigate('/reports'),
    },
    {
      key: 'progress',
      label: 'Progress',
      onClick: () => navigate('/progress'),
    },
  ];

  return (
    <Layout className="app-layout">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
          height: '100vh',
          background: '#0F0F1A',
          zIndex: 10,
        }}
      >
        <div className="logo" style={{ padding: '16px', textAlign: 'center', color: 'white', fontSize: '18px' }}>
          CFS-Quant
        </div>
        <Button
          type="text"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={toggleCollapsed}
          style={{
            position: 'absolute',
            top: 80,
            right: -25,
            zIndex: 1,
            background: '#0F0F1A',
            color: 'white',
            border: 'none',
          }}
        />
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={['dashboard']}
          items={menuItems}
          style={{
            marginTop: '40px',
            backgroundColor: '#0F0F1A',
            borderRight: 'none',
          }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'margin-left 0.3s' }}>
        <Content style={{ padding: '24px', minHeight: '100vh', background: '#0A0A15' }}>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/strategy" element={<Strategy />} />
            <Route path="/tuning" element={<Tuning />} />
            <Route path="/monitor" element={<Monitor />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/progress" element={<Progress />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;