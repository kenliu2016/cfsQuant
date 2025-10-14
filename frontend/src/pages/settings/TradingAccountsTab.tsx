import React, { useEffect, useState } from 'react';
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



const TradingAccountsTab: React.FC = () => {
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [form] = Form.useForm();
  const { tenantId } = useTenant();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_admin || user?.is_super_admin);
  const [tenantUsers, setTenantUsers] = useState<{ value: string; label: string }[]>([]);

  const fetchAccounts = async () => {
    try {
      setLoading(true);
      const response = await client.get('/api/live-trading/accounts');
      setAccounts(response.data?.rows || []);
    } catch (error) {
      message.error('加载交易账户失败');
    } finally {
      setLoading(false);
    }
  };



  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // 并行获取账户和交易所数据
        const [accountsResponse, exchangesResponse] = await Promise.all([
          client.get('/api/live-trading/accounts'),
          client.get('/api/live-trading/exchanges')
        ]);
        
        setAccounts(accountsResponse.data?.rows || []);
        setExchanges(exchangesResponse.data?.exchanges || []);
        
        // 如果是管理员，获取租户用户数据
        if (isAdmin) {
          try {
            const usersResponse = await client.get('/api/users');
            const rows = usersResponse.data?.rows || [];
            setTenantUsers(
              rows.map((u: any) => ({ value: u.id, label: `${u.email}${u.is_admin ? ' (管理员)' : ''}` }))
            );
          } catch (error) {
            console.warn('加载租户用户失败', error);
          }
        }
      } catch (error) {
        message.error('加载交易账户失败');
      } finally {
        setLoading(false);
      }
    };
    
    // 只有在tenantId和isAdmin有实际变化时才执行
    if (tenantId) {
      void fetchData();
    }
  }, [tenantId, isAdmin]);

  const handleCreate = async () => {
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
      
      // 重新获取账户数据
      await fetchAccounts();
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.response?.data?.detail || '创建交易账户失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (accountId: string) => {
    try {
      await client.delete(`/api/live-trading/accounts/${accountId}`);
      message.success('交易账户已删除');
      
      // 重新获取账户数据
      await fetchAccounts();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '删除交易账户失败');
    }
  };

  const handleToggle = async (record: TradingAccount, value: boolean) => {
    try {
      await client.patch(`/api/live-trading/accounts/${record.id}`, { is_active: value });
      message.success('账户状态已更新');
      
      // 重新获取账户数据
      await fetchAccounts();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '更新账户状态失败');
    }
  };

  const handleTest = async (accountId: string) => {
    try {
      setTesting(accountId);
      await client.post(`/api/live-trading/accounts/${accountId}/test`);
      message.success('连接测试成功');
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '连接测试失败');
    } finally {
      setTesting(null);
    }
  };

  const columns = [
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
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="实时交易账户"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={async () => {
            try {
              setLoading(true);
              
              // 并行获取账户和交易所数据
              const [accountsResponse, exchangesResponse] = await Promise.all([
                client.get('/api/live-trading/accounts'),
                client.get('/api/live-trading/exchanges')
              ]);
              
              setAccounts(accountsResponse.data?.rows || []);
              setExchanges(exchangesResponse.data?.exchanges || []);
              
              // 如果是管理员，获取租户用户数据
              if (isAdmin) {
                try {
                  const usersResponse = await client.get('/api/users');
                  const rows = usersResponse.data?.rows || [];
                  setTenantUsers(
                    rows.map((u: any) => ({ value: u.id, label: `${u.email}${u.is_admin ? ' (管理员)' : ''}` }))
                  );
                } catch (error) {
                  console.warn('加载租户用户失败', error);
                }
              }
            } catch (error) {
              message.error('刷新数据失败');
            } finally {
              setLoading(false);
            }
          }} loading={loading}>
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
            <Select placeholder="请选择交易所">
              {exchanges.map((exchange) => (
                <Select.Option key={exchange} value={exchange}>
                  {exchange}
                </Select.Option>
              ))}
            </Select>
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
