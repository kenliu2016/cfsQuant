import React, { useMemo, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, message, Space, Tag, Switch, Tooltip } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import client from '../../api/client';
import { useTenant, TenantRecord } from '../../context/TenantContext';

const TenantsTab: React.FC = () => {
  const { tenants, refreshTenants, setTenantId, tenantId } = useTenant();
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();

  const dataSource = useMemo(() => tenants, [tenants]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setCreating(true);
      await client.post('/api/tenants', values);
      message.success('租户创建成功');
      setModalVisible(false);
      form.resetFields();
      await refreshTenants();
      setTenantId(values.tenant_id);
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.response?.data?.detail || '创建租户失败');
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (record: TenantRecord, value: boolean) => {
    if (record.tenant_id === 'public') {
      message.warning('默认租户无法停用');
      return;
    }
    try {
      setLoading(true);
      await client.patch(`/api/tenants/${record.tenant_id}`, { is_active: value });
      message.success('租户状态已更新');
      if (!value && record.tenant_id === tenantId) {
        // 如果禁用了当前租户，切换到public
        setTenantId('public');
      }
      await refreshTenants();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '更新租户状态失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '租户ID',
      dataIndex: 'tenant_id',
      key: 'tenant_id',
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: TenantRecord) => text || record.tenant_id,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (_: boolean, record: TenantRecord) => (
        <Space>
          <Switch
            checked={record.is_active !== false}
            disabled={record.tenant_id === 'public'}
            onChange={(value) => handleToggleActive(record, value)}
          />
          {record.tenant_id === tenantId && <Tag color="blue">当前</Tag>}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: TenantRecord) => (
        <Space>
          <Tooltip title="切换到此租户">
            <Button size="small" type="link" onClick={() => setTenantId(record.tenant_id)}>
              切换
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="租户管理"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refreshTenants()} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            新增租户
          </Button>
        </Space>
      }
      style={{ height: 'calc(100vh - 180px)' }}
      bodyStyle={{ height: 'calc(100% - 56px)', overflow: 'auto' }}
    >
      <Table
        dataSource={dataSource}
        loading={loading}
        rowKey={(record) => record.tenant_id}
        columns={columns}
        pagination={false}
      />

      <Modal
        open={modalVisible}
        title="创建租户"
        onCancel={() => setModalVisible(false)}
        onOk={handleCreate}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
      >
        <Form layout="vertical" form={form}>
          <Form.Item
            label="租户ID"
            name="tenant_id"
            rules={[{ required: true, message: '请输入租户ID' }]}
          >
            <Input placeholder="唯一租户标识" />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="名称" />
          </Form.Item>
          <Form.Item
            label="管理员邮箱"
            name="admin_email"
            rules={[{ required: true, message: '请输入管理员邮箱' }, { type: 'email', message: '请输入有效的邮箱地址' }]}
          >
            <Input placeholder="管理员邮箱" />
          </Form.Item>
          <Form.Item
            label="管理员密码"
            name="admin_password"
            rules={[{ required: true, message: '请输入管理员密码' }, { min: 6, message: '密码至少6位' }]}
          >
            <Input.Password placeholder="管理员密码" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="描述" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default TenantsTab;
