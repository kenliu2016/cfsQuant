import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, Checkbox, message, Popconfirm, Select } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, SyncOutlined, EyeInvisibleOutlined, EyeOutlined, DatabaseOutlined, SearchOutlined } from '@ant-design/icons';
import client from '../api/client';

// 定义交易对的接口
interface MarketCode {
  exchange: string;
  code: string;
  excode: string;
  active: boolean;
  watch: boolean;
}

const Settings: React.FC = () => {
  const [marketCodes, setMarketCodes] = useState<MarketCode[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [isAddModalVisible, setIsAddModalVisible] = useState<boolean>(false);
  const [isEditModalVisible, setIsEditModalVisible] = useState<boolean>(false);
  const [currentCode, setCurrentCode] = useState<MarketCode | null>(null);
  const [addForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [exchangeFilter, setExchangeFilter] = useState<string>('');
  const [codeFilter, setCodeFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(15);

  // 加载交易对数据
  const loadMarketCodes = async () => {
    setLoading(true);
    try {
      const response = await client.get('/api/market/market_codes', {
        params: {
          active: null, // 获取所有代码，包括非活跃的
          exchange: exchangeFilter || undefined,
          code: codeFilter || undefined,
          page: currentPage,
          page_size: pageSize
        }
      });
      setMarketCodes(response.data.rows || []);
    } catch (error) {
      console.error('加载交易对失败:', error);
      message.error('加载交易对失败');
    } finally {
      setLoading(false);
    }
  };

  // 初始化时加载数据
  useEffect(() => {
    loadMarketCodes();
  }, []);

  // 刷新数据
  const handleRefresh = () => {
    loadMarketCodes();
    setSelectedRowKeys([]);
  };

  // 应用过滤
  const handleFilter = () => {
    loadMarketCodes();
    setSelectedRowKeys([]);
  };

  // 过滤观察交易对
  const handleWatchFilter = (value: boolean) => {
    setCurrentPage(1);
    // 保存原始请求参数结构，但通过接口传递watch参数
    const fetchFilteredCodes = async () => {
      setLoading(true);
      try {
        const response = await client.get('/api/market/market_codes', {
          params: {
            active: null,
            watch: value,
            page: 1,
            page_size: pageSize
          }
        });
        setMarketCodes(response.data.rows || []);
      } catch (error) {
        console.error('加载交易对失败:', error);
        message.error('加载交易对失败');
      } finally {
        setLoading(false);
      }
    };
    fetchFilteredCodes();
    setSelectedRowKeys([]);
  };

  // 过滤接入交易对
  const handleActiveFilter = (value: boolean) => {
    setCurrentPage(1);
    // 保存原始请求参数结构，但通过接口传递active参数
    const fetchFilteredCodes = async () => {
      setLoading(true);
      try {
        const response = await client.get('/api/market/market_codes', {
          params: {
            active: value,
            watch: null,
            page: 1,
            page_size: pageSize
          }
        });
        setMarketCodes(response.data.rows || []);
      } catch (error) {
        console.error('加载交易对失败:', error);
        message.error('加载交易对失败');
      } finally {
        setLoading(false);
      }
    };
    fetchFilteredCodes();
    setSelectedRowKeys([]);
  };

  // 重置过滤
  const handleResetFilter = () => {
    setExchangeFilter('');
    setCodeFilter('');
    setCurrentPage(1);
    setPageSize(15);
    loadMarketCodes();
    setSelectedRowKeys([]);
  };

  // 处理分页变化
  const handlePageChange = (page: number, newPageSize: number) => {
    setCurrentPage(page);
    setPageSize(newPageSize);
    loadMarketCodes();
  };

  // 处理每页条数变化
  const handleShowSizeChange = (_current: number, size: number) => {
    setCurrentPage(1);
    setPageSize(size);
    loadMarketCodes();
  };

  // 打开添加模态框
  const handleAddModalOpen = () => {
    addForm.resetFields();
    setIsAddModalVisible(true);
  };

  // 打开编辑模态框
  const handleEditModalOpen = (record: MarketCode) => {
    setCurrentCode(record);
    editForm.setFieldsValue({
      exchange: record.exchange,
      code: record.code,
      excode: record.excode,
      active: record.active,
      watch: record.watch
    });
    setIsEditModalVisible(true);
  };

  // 添加交易对
  const handleAdd = async (values: any) => {
    try {
      await client.post('/api/market/market_codes', values);
      message.success('添加成功');
      setIsAddModalVisible(false);
      loadMarketCodes();
    } catch (error) {
      console.error('添加失败:', error);
      message.error('添加失败');
    }
  };

  // 更新交易对
  const handleUpdate = async (values: any) => {
    if (!currentCode) return;
    
    try {
      await client.put(`/api/market/market_codes/${encodeURIComponent(currentCode.exchange)}/${encodeURIComponent(currentCode.code)}`, values);
      message.success('更新成功');
      setIsEditModalVisible(false);
      loadMarketCodes();
    } catch (error) {
      console.error('更新失败:', error);
      message.error('更新失败');
    }
  };

  // 删除交易对
  const handleDelete = async (exchange: string, code: string) => {
    try {
      await client.delete(`/api/market/market_codes/${encodeURIComponent(exchange)}/${encodeURIComponent(code)}`);
      message.success('删除成功');
      loadMarketCodes();
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败');
    }
  };

  // 批量设置观察
  const handleBatchSetWatch = async (watch: boolean) => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要操作的行');
      return;
    }

    try {
      await client.post('/api/market/market_codes/batch_update', {
        keys: selectedRowKeys,
        updates: { watch }
      });
      message.success(`批量${watch ? '设置观察' : '取消观察'}成功`);
      loadMarketCodes();
      setSelectedRowKeys([]);
    } catch (error) {
      console.error('批量操作失败:', error);
      message.error('批量操作失败');
    }
  };

  // 批量设置数据接入
  const handleBatchSetActive = async (active: boolean) => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要操作的行');
      return;
    }

    try {
      await client.post('/api/market/market_codes/batch_update', {
        keys: selectedRowKeys,
        updates: { active }
      });
      message.success(`批量${active ? '设置数据接入' : '取消数据接入'}成功`);
      loadMarketCodes();
      setSelectedRowKeys([]);
    } catch (error) {
      console.error('批量操作失败:', error);
      message.error('批量操作失败');
    }
  };

  // 表格的列配置
  const columns = [
    {
      title: '交易所',
      dataIndex: 'exchange',
      key: 'exchange',
    },
    {
      title: '代码',
      dataIndex: 'code',
      key: 'code',
    },
    {
      title: '交易所代码',
      dataIndex: 'excode',
      key: 'excode',
    },
    {
      title: '数据接入',
      dataIndex: 'active',
      key: 'active',
      render: (text: boolean) => (
        <Checkbox checked={text} disabled>
          {text ? '是' : '否'}
        </Checkbox>
      ),
    },
    {
      title: '观察',
      dataIndex: 'watch',
      key: 'watch',
      render: (text: boolean) => (
        <Checkbox checked={text} disabled>
          {text ? '是' : '否'}
        </Checkbox>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: MarketCode) => (
        <span>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEditModalOpen(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个交易对吗？"
            onConfirm={() => handleDelete(record.exchange, record.code)}
            okText="是"
            cancelText="否"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </span>
      ),
    },
  ];

  // 行选择配置
  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
  };

  return (
    <div style={{ padding: '10px', height: '100vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <Card title="交易对管理" extra={
          <Button type="primary" icon={<PlusOutlined />} size="small" onClick={handleAddModalOpen}>
            添加
          </Button>
        } style={{ flex: '1', display: 'flex', flexDirection: 'column', marginBottom: '0' }}>
        {/* 过滤条件输入 */}
        <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
          <Select
            placeholder="按交易所过滤"
            value={exchangeFilter || undefined}
            onChange={(value) => setExchangeFilter(value || '')}
            style={{ width: '160px' }}
            size="small"
            allowClear
          >
            <Select.Option value="binance">binance</Select.Option>
            <Select.Option value="bybit">bybit</Select.Option>
            <Select.Option value="coinbase">coinbase</Select.Option>
            <Select.Option value="upbit">upbit</Select.Option>
            <Select.Option value="okx">okx</Select.Option>
          </Select>
          <Input
            placeholder="按交易对过滤"
            value={codeFilter}
            onChange={(e) => setCodeFilter(e.target.value)}
            style={{ width: '160px' }}
            size="small"
          />
          <Button
            type="primary"
            size="small"
            icon={<SearchOutlined />}
            onClick={handleFilter}
          >
            搜索
          </Button>
          <Button onClick={handleResetFilter} size="small">
            重置
          </Button>
          <Button
            size="small"
            onClick={() => handleWatchFilter(true)}
          >
            所有观察交易对
          </Button>
          <Button
            size="small"
            onClick={() => handleActiveFilter(true)}
          >
            所有接入交易对
          </Button>
          <Button
            icon={<SyncOutlined />}
            size="small"
            onClick={handleRefresh}
            loading={loading}
            style={{ marginRight: '6px' }}
          >
            刷新
          </Button>
        </div>

        {/* 批量操作按钮 */}
        <div style={{ marginBottom: '8px', textAlign: 'right' }}>
          <Button
            icon={<EyeOutlined />}
            size="small"
            onClick={() => handleBatchSetWatch(true)}
            disabled={selectedRowKeys.length === 0}
            style={{ marginRight: '6px' }}
          >
            批量设置观察
          </Button>
          <Button
            icon={<EyeInvisibleOutlined />}
            size="small"
            onClick={() => handleBatchSetWatch(false)}
            disabled={selectedRowKeys.length === 0}
            style={{ marginRight: '6px' }}
          >
            批量取消观察
          </Button>
          <Button
            type="primary"
            size="small"
            icon={<DatabaseOutlined />}
            onClick={() => handleBatchSetActive(true)}
            disabled={selectedRowKeys.length === 0}
            style={{ marginRight: '6px' }}
          >
            批量设置数据接入
          </Button>
          <Button
            danger
            size="small"
            icon={<DatabaseOutlined />}
            onClick={() => handleBatchSetActive(false)}
            disabled={selectedRowKeys.length === 0}
          >
            批量取消数据接入
          </Button>
        </div>

        {/* 交易对表格 */}
        <div style={{ flex: '1', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <Table
            rowSelection={rowSelection}
            columns={columns}
            dataSource={marketCodes}
            rowKey={(record) => `${record.exchange}:${record.code}`}
            loading={loading}
            pagination={{
              current: currentPage,
              pageSize: pageSize,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条记录`,
              onChange: handlePageChange,
              onShowSizeChange: handleShowSizeChange
            }}
            scroll={{ y: 'calc(100vh - 280px)' }}
            size="middle"
          />
        </div>
      </Card>

      {/* 添加交易对模态框 */}
      <Modal
        title="添加交易对"
        open={isAddModalVisible}
        onCancel={() => setIsAddModalVisible(false)}
        footer={null}
      >
        <Form
          form={addForm}
          layout="vertical"
          onFinish={handleAdd}
        >
          <Form.Item
            name="exchange"
            label="交易所"
            rules={[{ required: true, message: '请输入交易所' }]}
          >
            <Input placeholder="请输入交易所" />
          </Form.Item>
          <Form.Item
            name="code"
            label="代码"
            rules={[{ required: true, message: '请输入代码' }]}
          >
            <Input placeholder="请输入代码" />
          </Form.Item>
          <Form.Item
            name="excode"
            label="交易所代码"
            rules={[{ required: true, message: '请输入交易所代码' }]}
          >
            <Input placeholder="请输入交易所代码" />
          </Form.Item>
          <Form.Item name="active" label="数据接入" valuePropName="checked">
            <Checkbox>是否启用数据接入</Checkbox>
          </Form.Item>
          <Form.Item name="watch" label="观察" valuePropName="checked">
            <Checkbox>是否设为观察</Checkbox>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" style={{ marginRight: '10px' }}>
              添加
            </Button>
            <Button onClick={() => setIsAddModalVisible(false)}>
              取消
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑交易对模态框 */}
      <Modal
        title="编辑交易对"
        open={isEditModalVisible}
        onCancel={() => setIsEditModalVisible(false)}
        footer={null}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Form.Item name="exchange" label="交易所">
            <Input disabled />
          </Form.Item>
          <Form.Item name="code" label="代码">
            <Input disabled />
          </Form.Item>
          <Form.Item name="excode" label="交易所代码">
            <Input disabled />
          </Form.Item>
          <Form.Item name="active" label="数据接入" valuePropName="checked">
            <Checkbox>是否启用数据接入</Checkbox>
          </Form.Item>
          <Form.Item name="watch" label="观察" valuePropName="checked">
            <Checkbox>是否设为观察</Checkbox>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" style={{ marginRight: '10px' }}>
              保存
            </Button>
            <Button onClick={() => setIsEditModalVisible(false)}>
              取消
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Settings;