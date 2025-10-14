import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Checkbox,
  Space,
  Switch,
  message,
  Tooltip,
} from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import client from '../../api/client';
import { useTenant } from '../../context/TenantContext';
import { useAuth } from '../../context/AuthContext';

interface TenantUser {
  id: string;
  tenant_id: string;
  email: string;
  full_name?: string;
  is_admin?: boolean;
  is_super_admin?: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

const TenantUsersTab: React.FC = () => {
  const { tenantId, refreshTenants } = useTenant();
  const { user } = useAuth();
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

  const isSuperAdmin = Boolean(user?.is_super_admin);

  useEffect(() => {
    const fetchUsers = async () => {
      setLoading(true);
      try {
        const response = await client.get('/api/users');
        setUsers(response.data?.rows || []);
      } catch (error) {
        message.error('加载用户列表失败');
      } finally {
        setLoading(false);
      }
    };
    
    void fetchUsers();
  }, [tenantId]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setCreating(true);
      await client.post('/api/users', values);
      message.success('用户创建成功');
      setModalVisible(false);
      form.resetFields();
      // 重新获取用户列表
      setLoading(true);
      const response = await client.get('/api/users');
      setUsers(response.data?.rows || []);
      await refreshTenants();
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.response?.data?.detail || '创建用户失败');
    } finally {
      setCreating(false);
      setLoading(false);
    }
  };

  const handleToggleActive = async (record: TenantUser, value: boolean) => {
    try {
      await client.patch(`/api/users/${record.id}`, { is_active: value });
      message.success('用户状态已更新');
      // 重新获取用户列表
      setLoading(true);
      const response = await client.get('/api/users');
      setUsers(response.data?.rows || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '更新用户状态失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = useMemo(
    () => [
      {
        title: '邮箱',
        dataIndex: 'email',
        key: 'email',
      },
      {
        title: '姓名',
        dataIndex: 'full_name',
        key: 'full_name',
      },
      {
        title: '角色',
        dataIndex: 'is_admin',
        key: 'role',
        render: (_: any, record: TenantUser) => {
          if (record.is_super_admin) return '超级管理员';
          if (record.is_admin) return '租户管理员';
          return '普通用户';
        },
      },
      {
        title: '状态',
        dataIndex: 'is_active',
        key: 'is_active',
        render: (_: boolean, record: TenantUser) => (
          <Switch
            checked={record.is_active !== false}
            onChange={(value) => handleToggleActive(record, value)}
            disabled={record.id === user?.id || record.is_super_admin}
          />
        ),
      },
      {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
      },
    ],
    [user],
  );

  return (
    <Card
      title="用户管理"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => {
            setLoading(true);
            client.get('/api/users').then(response => {
              setUsers(response.data?.rows || []);
            }).catch(error => {
              message.error('加载用户列表失败');
            }).finally(() => {
              setLoading(false);
            });
          }} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            新增用户
          </Button>
        </Space>
      }
      style={{ height: 'calc(100vh - 180px)' }}
      bodyStyle={{ height: 'calc(100% - 56px)', overflow: 'auto' }}
    >
      <Table
        dataSource={users}
        loading={loading}
        rowKey={(record) => record.id}
        columns={columns}
        pagination={false}
      />

      <Modal
        open={modalVisible}
        title="创建用户"
        onCancel={() => setModalVisible(false)}
        onOk={handleCreate}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
      >
        <Form layout="vertical" form={form} initialValues={{ is_admin: false }}>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少6位' }]}
          >
            <Input.Password placeholder="至少6位密码" />
          </Form.Item>
          <Form.Item label="姓名" name="full_name">
            <Input placeholder="用户姓名（可选）" />
          </Form.Item>
          <Form.Item name="is_admin" valuePropName="checked">
            <Checkbox>设为租户管理员</Checkbox>
          </Form.Item>
          {isSuperAdmin && (
            <Tooltip title="仅超级管理员可创建超级管理员">
              <Form.Item name="is_super_admin" valuePropName="checked">
                <Checkbox>设为超级管理员</Checkbox>
              </Form.Item>
            </Tooltip>
          )}
        </Form>
      </Modal>
    </Card>
  );
};

export default TenantUsersTab;
