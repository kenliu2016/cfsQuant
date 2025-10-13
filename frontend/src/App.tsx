import React, { useState } from 'react';
import { Layout, Menu, Button, Space } from 'antd';
import { MenuFoldOutlined, MenuUnfoldOutlined, LogoutOutlined } from '@ant-design/icons';
import { Routes, Route, useNavigate, Navigate, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Strategy from './pages/Strategy';
import Tuning from './pages/Tuning';
import Reports from './pages/Reports';
import Progress from './pages/Progress';
import ReportDetail from './pages/ReportDetail';
import Settings from './pages/Settings';
import './custom-menu.css';
import TenantSelector from './components/TenantSelector';
import Login from './pages/Login';
import { useAuth } from './context/AuthContext';

const { Sider, Content, Header } = Layout;

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(true);
  const navigate = useNavigate();
  const { logout } = useAuth();

  const toggleCollapsed = () => {
    setCollapsed(!collapsed);
  };

  // 定义菜单项
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
      key: 'reports',
      label: 'Reports',
      onClick: () => navigate('/reports'),
    },
    {
      key: 'tuning',
      label: 'Tuning',
      onClick: () => navigate('/tuning'),
    },
    {
      key: 'progress',
      label: 'Progress',
      onClick: () => navigate('/progress'),
    },
    {
      key: 'settings',
      label: 'Settings',
      onClick: () => navigate('/settings'),
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
        <Button
          type="text"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={toggleCollapsed}
          style={{
              position: 'absolute',
              top: 7,
              right: 0,
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
            marginTop: '0px',
            backgroundColor: '#0F0F1A',
            borderRight: 'none'
          }}
          className="custom-menu"
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'margin-left 0.3s' }}>
        <Header
          style={{
            background: '#0A0A15',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0 24px',
          }}
        >
          <div style={{ color: '#fff', fontWeight: 600 }}>SaaS Quant Dashboard</div>
          <Space>
            <TenantSelector />
            <Button icon={<LogoutOutlined />} onClick={logout}>
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ padding: 0, minHeight: 'calc(100vh - 64px)', background: '#0A0A15' }}>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/strategy" element={<Strategy />} />
            <Route path="/tuning" element={<Tuning />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/reports/:runId" element={<ReportDetail />} />
            <Route path="/progress" element={<Progress />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

const PrivateRoute: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <AppLayout />;
};

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<PrivateRoute />} />
    </Routes>
  );
};

export default App;
