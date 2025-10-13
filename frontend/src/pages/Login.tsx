import React, { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { LockOutlined, UserOutlined, ApartmentOutlined } from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import { useTenant } from '../context/TenantContext';
import { useLocation, useNavigate, Location } from 'react-router-dom';

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const { login, loading } = useAuth();
  const { tenantId } = useTenant();
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const location = useLocation();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    form.setFieldsValue({ tenant_id: tenantId });
  }, [tenantId, form]);

  const handleFinish = async (values: { tenant_id: string; email: string; password: string }) => {
    try {
      setErrorMessage(null);
      await login(values.tenant_id, values.email, values.password);
      message.success('登录成功');
      const target = (location.state as { from?: Location })?.from?.pathname || '/dashboard';
      navigate(target, { replace: true });
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '登录失败，请检查账号和密码';
      setErrorMessage(detail);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0A0A15' }}>
      <Card style={{ width: 380, padding: '24px 16px' }}>
        <Title level={3} style={{ textAlign: 'center' }}>
          系统登录
        </Title>
        <Form
          layout="vertical"
          form={form}
          initialValues={{ tenant_id: tenantId }}
          onFinish={handleFinish}
        >
          <Form.Item
            label="租户 ID"
            name="tenant_id"
            rules={[{ required: true, message: '请输入租户ID' }]}
          >
            <Input prefix={<ApartmentOutlined />} placeholder="tenant id" />
          </Form.Item>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[{ required: true, message: '请输入邮箱' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="email" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="password" />
          </Form.Item>
          {errorMessage && (
            <Text type="danger" style={{ marginBottom: 12, display: 'block' }}>
              {errorMessage}
            </Text>
          )}
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
        <Text type="secondary">开通新租户请联系管理员或使用租户接口进行注册。</Text>
      </Card>
    </div>
  );
};

export default Login;
