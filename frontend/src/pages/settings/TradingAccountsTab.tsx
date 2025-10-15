import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Space,
  message,
  Switch,
  Popconfirm,
} from 'antd';
import { PlusOutlined, ReloadOutlined, ThunderboltOutlined, DeleteOutlined } from '@ant-design/icons';
import client from '../../api/client';
import { useTenant } from '../../context/TenantContext';
import { useAuth } from '../../context/AuthContext';

interface TradingAccount {
  id: string;
  exchange: string;
  label?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  api_key_preview?: string;
  owner_user_id?: string | null;
}

interface TenantUserOption {
  value: string;
  label: string;
}

const TradingAccountsTab: React.FC = () => {
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [tenantUsers, setTenantUsers] = useState<TenantUserOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [form] = Form.useForm();
  const { tenantId } = useTenant();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_admin || user?.is_super_admin);

  const loadData = useCallback(async () => {
    console.log('loadData called, tenantId:', tenantId, 'isAdmin:', isAdmin);
    setLoading(true);
    try {
      const requests: Promise<any>[] = [
        client.get('/api/live-trading/accounts'),
        client.get('/api/live-trading/exchanges'),
      ];
      if (isAdmin) {
        requests.push(client.get('/api/users'));
      }
      const [accountsRes, exchangesRes, usersRes] = await Promise.all(requests);
      setAccounts(accountsRes.data?.rows || []);
      setExchanges(exchangesRes.data?.exchanges || []);
      if (isAdmin && usersRes) {
        const rows = usersRes.data?.rows || [];
        setTenantUsers(
          rows.map((u: any) => ({ value: u.id, label: `${u.email}${u.is_admin ? ' (管理员)' : ''}` })),
        );
      }
    } catch (error) {
      message.error('加载交易账户失败');
    } finally {
      setLoading(false);
    }
  }, [isAdmin, tenantId]);

  useEffect(() => {
    if (tenantId) {
      void loadData();
    }
  }, [loadData, tenantId]);

  const handleCreate = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const payload: Record<string, any> = { ...values };
      if (payload.extra) {
        try {
          payload.extra = JSON.parse(payload.extra);
        } catch (error) {
          message.error('附加配置必须是合法的JSON');
          return;
        }
      }
      setSaving(true);
      await client.post('/api/live-trading/accounts', payload);
      message.success('交易账户创建成功');
      setModalVisible(false);
      form.resetFields();
      await loadData();
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.response?.data?.detail || '创建交易账户失败');
    } finally {
      setSaving(false);
    }
  }, [form, loadData]);

  const handleDelete = useCallback(
    async (accountId: string) => {
      try {
        await client.delete(`/api/live-trading/accounts/${accountId}`);
        message.success('交易账户已删除');
        await loadData();
      } catch (error: any) {
        message.error(error?.response?.data?.detail || '删除交易账户失败');
      }
    },
    [loadData],
  );

  const handleToggle = useCallback(
    async (record: TradingAccount, value: boolean) => {
      try {
        await client.patch(`/api/live-trading/accounts/${record.id}`, { is_active: value });
        message.success('账户状态已更新');
        await loadData();
      } catch (error: any) {
        message.error(error?.response?.data?.detail || '更新账户状态失败');
      }
    },
    [loadData],
  );

  const handleTest = useCallback(async (accountId: string) => {
    try {
      setTesting(accountId);
      await client.post(`/api/live-trading/accounts/${accountId}/test`);
      message.success('连接测试成功');
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '连接测试失败');
    } finally {
      setTesting(null);
    }
  }, []);

  const columns = useMemo(
    () => [
      {
        title: '标签',
        dataIndex: 'label',
        key: 'label',
        render: (text: string, record: TradingAccount) => text || record.exchange,
      },
      {
        title: '交易所',
        dataIndex: 'exchange',
        key: 'exchange',
      },
      {
        title: '状态',
        dataIndex: 'is_active',
        key: 'is_active',
        render: (_: any, record: TradingAccount) => (
          <Switch checked={record.is_active !== false} onChange={(value) => handleToggle(record, value)} />
        ),
      },
      {
        title: 'API Key',
        dataIndex: 'api_key_preview',
        key: 'api_key_preview',
        render: (text: string) => text || '已配置',
      },
      ...(isAdmin
        ? [
            {
              title: '归属用户',
              dataIndex: 'owner_user_id',
              key: 'owner_user_id',
              render: (value: string | null) => {
                const match = tenantUsers.find((u) => u.value === value);
                return match?.label || '当前用户';
              },
            },
          ]
        : []),
      {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
      },
      {
        title: '操作',
        key: 'actions',
        render: (_: unknown, record: TradingAccount) => (
          <Space>
            <Button
              type="link"
              size="small"
              icon={<ThunderboltOutlined />}
              loading={testing === record.id}
              onClick={() => handleTest(record.id)}
            >
              测试
            </Button>
            <Popconfirm
              title="确定删除该交易账户?"
              onConfirm={() => handleDelete(record.id)}
              okText="删除"
              cancelText="取消"
            >
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [handleDelete, handleTest, handleToggle, isAdmin, tenantUsers, testing],
  );

  return (
    <Card
      title="实时交易账户"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            新增账户
          </Button>
        </Space>
      }
      style={{ height: 'calc(100vh - 180px)' }}
      bodyStyle={{ height: 'calc(100% - 56px)', overflow: 'auto' }}
    >
      <Table
        dataSource={accounts}
        loading={loading}
        rowKey={(record) => record.id}
        columns={columns}
        pagination={false}
      />

      <Modal
        open={modalVisible}
        title="新建交易账户"
        onCancel={() => setModalVisible(false)}
        onOk={handleCreate}
        okText="保存"
        confirmLoading={saving}
      >
        <Form layout="vertical" form={form}>
          <Form.Item label="标签" name="label">
            <Input placeholder="用于辨识账户，可选" />
          </Form.Item>
          <Form.Item label="交易所" name="exchange" rules={[{ required: true, message: '请选择交易所' }]}>
            <Select placeholder="请选择交易所" options={exchanges.map((ex) => ({ value: ex, label: ex }))} />
          </Form.Item>
          <Form.Item label="API Key" name="api_key" rules={[{ required: true, message: '请输入API Key' }]}>
            <Input placeholder="API Key" />
          </Form.Item>
          <Form.Item label="API Secret" name="api_secret" rules={[{ required: true, message: '请输入API Secret' }]}>
            <Input.Password placeholder="API Secret" />
          </Form.Item>
          <Form.Item label="Passphrase" name="api_passphrase">
            <Input placeholder="部分交易所需要的Passphrase" />
          </Form.Item>
          <Form.Item label="附加配置" name="extra" tooltip="JSON格式，例如 { &quot;options&quot;: { ... } }">
            <Input.TextArea placeholder="JSON格式的附加配置，可选" rows={3} />
          </Form.Item>
          <Form.Item label="启用状态" name="is_active" valuePropName="checked" initialValue>
            <Switch />
          </Form.Item>
          {isAdmin && (
            <Form.Item label="归属用户" name="owner_user_id">
              <Select placeholder="默认归属当前用户" allowClear options={tenantUsers} />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </Card>
  );
};

export default TradingAccountsTab;
