import client from '../api/client'
import dayjs from 'dayjs'
import { useState, useEffect, useCallback } from 'react'
import { Form, Row, Col, Card, Button, Select, InputNumber, List, Progress, message, Tooltip, Input, DatePicker } from 'antd'
import { InfoCircleOutlined, SettingOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

// 定义参数配置类型
interface ParamConfig {
  default: any;
  min?: number;
  max?: number;
  step?: number;
  type?: 'boolean' | 'number'; // 参数类型标识
}

// 定义范围配置类型
interface RangeConfig {
  min?: number;
  max?: number;
  step?: number;
  type: string;
  options?: any[];
  currentValue?: any;
}

export default function Tuning() {
  const [form] = Form.useForm();
  const [task, setTask] = useState<string | null>(null);
  const [status] = useState<{status?: string, total?: number, finished?: number, runs?: any[]} | null>(null);
  const [timer, setTimer] = useState<any>(null);
  const [symbols, setSymbols] = useState<{ value: string; label: string }[]>([]);
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([]);
  const [strategies, setStrategies] = useState<{ value: string; label: string }[]>([]);
  const [filteredStrategies, setFilteredStrategies] = useState<{ value: string; label: string }[]>([]);
  const [strategyParams, setStrategyParams] = useState<{[key: string]: ParamConfig}>({});
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  // 从API加载标的数据
  const loadSymbols = async () => {
    try {
      const response = await client.get('/api/market/market_codes');
      const marketCodes = response.data.rows || [];
      
      // 格式化数据为Select组件需要的格式，使用excode字段
      const symbolData = marketCodes.map((item: any) => ({
        value: item.excode, // 提交时使用的字段
        label: `${item.excode}` // 显示的标签
      }));
      
      setSymbols(symbolData);
      setFilteredSymbols(symbolData);
    } catch (error) {
      console.error('加载标的数据失败:', error);
    }
  }
  
  // 加载策略列表
  const loadStrategies = async () => {
    try {
      const response = await client.get('/api/strategies');
      const strategyList = response.data.rows || [];
      
      const strategyData = strategyList.map((strategy: any) => ({
        value: strategy.name,
        label: `${strategy.name}${strategy.description ? ` - ${strategy.description}` : ''}`
      }));
      
      setStrategies(strategyData);
      setFilteredStrategies(strategyData);
    } catch (error) {
      console.error('加载策略列表失败:', error);
    }
  }
  
  // 获取策略参数
  const loadStrategyParams = async (strategyName: string) => {
    try {
      const response = await client.get('/api/strategies');
      const strategyList = response.data.rows || [];
      const strategy = strategyList.find((s: any) => s.name === strategyName);
      
      if (strategy && strategy.params) {
        try {
          // 解析paras里的JSON字符串
          let params = {};
          if (typeof strategy.params === 'string') {
            // 如果是字符串，尝试解析为JSON对象
            try {
              params = JSON.parse(strategy.params);
            } catch (parseError) {
              console.error('解析策略参数JSON失败:', parseError);
              setStrategyParams({});
              return;
            }
          } else if (typeof strategy.params === 'object') {
            // 如果已经是对象，直接使用
            params = strategy.params;
          }
          
          // 构建参数配置对象 - 只保留默认值，不自动设置范围
          const paramsConfig: {[key: string]: ParamConfig} = {};
          
          Object.entries(params).forEach(([key, value]) => {
            paramsConfig[key] = {
              default: value,
              // 记录参数类型，用于渲染不同的控件
              type: typeof value === 'boolean' ? 'boolean' : 'number'
            };
          });
          
          setStrategyParams(paramsConfig);
          
          // 清除之前的参数设置
          form.setFieldValue('paramsConfig', {});
        } catch (jsonError) {
          console.error('处理策略参数失败:', jsonError);
          setStrategyParams({});
        }
      } else {
        setStrategyParams({});
      }
    } catch (error) {
      console.error('获取策略参数失败:', error);
      setStrategyParams({});
    }
  }

  // 使用useCallback缓存搜索函数
  const handleSymbolSearch = useCallback((inputValue: string) => {
    if (!inputValue) {
      setFilteredSymbols(symbols);
      return;
    }
    
    const lowerInput = inputValue.toLowerCase();
    // 优化：预先转换输入值为小写，避免重复调用toLowerCase
    const filtered = symbols.filter(symbol => 
      symbol.value.toLowerCase().includes(lowerInput) ||
      symbol.label.toLowerCase().includes(lowerInput)
    );
    setFilteredSymbols(filtered);
  }, [symbols])
  
  // 使用useCallback缓存策略搜索函数
  const handleStrategySearch = useCallback((inputValue: string) => {
    if (!inputValue) {
      setFilteredStrategies(strategies);
      return;
    }
    
    const lowerInput = inputValue.toLowerCase();
    const filtered = strategies.filter(strategy => 
      strategy.value.toLowerCase().includes(lowerInput) ||
      strategy.label.toLowerCase().includes(lowerInput)
    );
    setFilteredStrategies(filtered);
  }, [strategies])
  
  // 处理策略选择变化
  const handleStrategyChange = (value: string) => {
    if (value) {
      loadStrategyParams(value);
    } else {
      setStrategyParams({});
    }
  }

  useEffect(()=>{
    // 初始化时加载标的数据和策略列表
    loadSymbols();
    loadStrategies();
    return ()=> { if (timer) clearInterval(timer) }
  },[timer])

  const onRun = async () => {
    // 设置加载状态，防止二次点击
    setIsLoading(true);
    
    try {
      const v = await form.validateFields()
      
      // 构建参数范围对象
      const paramsConfig = v.paramsConfig as {[key: string]: RangeConfig} || {};
      const paramsGrid: {[key: string]: any[]} = {};
      
      // 为每个参数创建值列表
      Object.entries(paramsConfig).forEach(([key, config]) => {
        const { min, max, step, type } = config as RangeConfig;
        
        if (type === 'range' && min !== undefined && max !== undefined && step !== undefined) {
          // 生成范围内的值列表
          const values: number[] = [];
          let current = min;
          while (current <= max) {
            values.push(current);
            // 避免浮点精度问题
            current = parseFloat((current + step).toFixed(10));
          }
          paramsGrid[key] = values;
        } else if (type === 'list' && Array.isArray(config.options)) {
          // 直接使用选项列表
          paramsGrid[key] = config.options;
        }
      });
      
      // 构建完整的参数配置JSON字符串，包含参数值、最大值、最小值、步长等信息
      const fullParamsConfigJSON = JSON.stringify(paramsConfig);
      
      const payload = { 
        strategy: v.strategy, 
        params: paramsGrid,
        params_config: fullParamsConfigJSON, // 添加完整的参数配置JSON字符串
        excode: v.code, // 使用excode字段提交
        start_time: v.range[0].format('YYYY-MM-DD HH:mm:ss'), 
        end_time: v.range[1].format('YYYY-MM-DD HH:mm:ss'), 
        interval: v.interval
      };
      
      const r = await client.post('/api/tuning', payload)
      const task_id = r.data.task_id
      setTask(task_id)
      message.success('任务已提交: ' + task_id)
      
      // 清除之前可能存在的定时器
      if (timer) {
        clearInterval(timer);
        setTimer(null);
      }
      
      // 跳转到Progress页面并传递task_id参数
      navigate(`/progress?task_id=${task_id}`)
    } catch (error) {
      console.error('提交寻优任务失败:', error);
      message.error('提交任务失败，请重试');
    } finally {
      // 无论成功失败，都重置加载状态
      setIsLoading(false);
    }
  }

  // 渲染参数设置表单
  const renderParamSettings = () => {
    if (Object.keys(strategyParams).length === 0) {
      return (
        <Card className="empty-state-card">
          <div className="empty-state-content">
            <InfoCircleOutlined className="empty-state-icon" />
            <p>请先选择策略</p>
          </div>
        </Card>
      );
    }
    
    return (
      <Card title="参数配置" className="params-config-card">
        <div className="params-config-scrollable">
          {Object.entries(strategyParams).map(([key, param]) => {
            const isBoolean = param.type === 'boolean';
            return (
              <Row key={key} gutter={[16, 16]} className="param-row" align="middle">
                <Col xs={24} sm={8} md={6} className="param-name">
                  <Tooltip title={`默认值: ${param.default}`}>
                    <div className="param-name-text">{key}</div>
                  </Tooltip>
                </Col>
                
                <Col xs={24} sm={16} md={4}>
                  <Form.Item
                    name={['paramsConfig', key, 'currentValue']}
                    initialValue={param.default}
                    noStyle
                  >
                    {isBoolean ? (
                      <Select className="param-value-select">
                        <Select.Option value={true}>True</Select.Option>
                        <Select.Option value={false}>False</Select.Option>
                      </Select>
                    ) : (
                      <InputNumber className="param-value-input" placeholder="值" />
                    )}
                  </Form.Item>
                </Col>
                
                {!isBoolean && (
                  <Col xs={24} md={14}>
                    <Row gutter={[8, 8]} align="middle">
                      <Col xs={8}>
                        <Form.Item
                          name={['paramsConfig', key, 'min']}
                          noStyle
                        >
                          <InputNumber min={0} placeholder="最小" className="param-range-input" />
                        </Form.Item>
                      </Col>
                      <Col xs={8}>
                        <Form.Item
                          name={['paramsConfig', key, 'max']}
                          noStyle
                        >
                          <InputNumber min={0} placeholder="最大" className="param-range-input" />
                        </Form.Item>
                      </Col>
                      <Col xs={8}>
                        <Form.Item
                          name={['paramsConfig', key, 'step']}
                          noStyle
                        >
                          <InputNumber min={0.0001} placeholder="步长" className="param-range-input" />
                        </Form.Item>
                      </Col>
                    </Row>
                  </Col>
                )}
                
                <Form.Item
                  name={['paramsConfig', key, 'type']}
                  initialValue={isBoolean ? 'list' : 'range'}
                  hidden
                  noStyle
                >
                  <Input />
                </Form.Item>
                
                {isBoolean && (
                  <Form.Item
                    name={['paramsConfig', key, 'options']}
                    initialValue={[true, false]}
                    hidden
                    noStyle
                  >
                    <Input />
                  </Form.Item>
                )}
              </Row>
            );
          })}
        </div>
      </Card>
    );
  };
  
  return (
    <div className="tuning-page">
      <Card title={<div className="card-title"><SettingOutlined className="title-icon" /> 参数寻优</div>} className="main-card">
        <Form form={form} layout="vertical" initialValues={{ 
          code: 'binance-BTC/USDT', 
          range: [dayjs().add(-30, 'day'), dayjs()],
          interval: '1m',
          paramsConfig: {} 
        }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} md={6}>
              <Form.Item label="策略" name="strategy" rules={[{required: true}]}>
                <Select
                  placeholder="请选择策略"
                  showSearch
                  filterOption={false}
                  onSearch={handleStrategySearch}
                  onChange={handleStrategyChange}
                  options={filteredStrategies}
                  className="form-select"
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item label="标的" name="code" rules={[{required: true}]}>
                <Select
                  placeholder="请选择或输入标的"
                  showSearch
                  filterOption={false}
                  onSearch={handleSymbolSearch}
                  options={filteredSymbols}
                  className="form-select"
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item label="时间间隔" name="interval">
                <Select className="form-select">
                  <Select.Option value="1m">1分钟</Select.Option>
                  <Select.Option value="5m">5分钟</Select.Option>
                  <Select.Option value="15m">15分钟</Select.Option>
                  <Select.Option value="30m">30分钟</Select.Option>
                  <Select.Option value="60m">60分钟</Select.Option>
                  <Select.Option value="1h">1小时</Select.Option>
                  <Select.Option value="4h">4小时</Select.Option>
                  <Select.Option value="1D">1天</Select.Option>
                  <Select.Option value="1W">1周</Select.Option>
                  <Select.Option value="1M">1月</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item label="区间" name="range" rules={[{required: true}]}>
                <DatePicker.RangePicker showTime className="form-datepicker" />
              </Form.Item>
            </Col>
          </Row>
        
          <div className="params-section">
            {renderParamSettings()}
          </div>
        
          <div className="action-section">
            <Button 
              type="primary" 
              onClick={onRun}
              disabled={Object.keys(strategyParams).length === 0 || isLoading}
              loading={isLoading}
              size="large"
              icon={<PlayCircleOutlined />}
              className="run-button"
            >
              开始寻优
            </Button>
          </div>
        </Form>

        {status && (
          <Card title="寻优状态" className="status-card" style={{marginTop: 16}}>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}>
                <div className="status-info">
                  <p className="status-label">任务ID:</p>
                  <p className="status-value">{task}</p>
                </div>
              </Col>
              <Col xs={24} md={8}>
                <div className="status-info">
                  <p className="status-label">当前状态:</p>
                  <p className="status-value">{status.status}</p>
                </div>
              </Col>
              <Col xs={24} md={8}>
                <div className="status-info">
                  <p className="status-label">进度:</p>
                  <p className="status-value">
                    {status.finished || 0}/{status.total || 0}
                  </p>
                </div>
              </Col>
            </Row>
            
            <Progress 
              percent={status.total && status.finished ? Math.round((status.finished / status.total) * 100) : 0} 
              strokeColor={{'0%': '#108ee9', '100%': '#87d068'}} 
              className="status-progress"
            />
            
            <List 
              size="small" 
              header={<div className="runs-header">已完成组合</div>} 
              dataSource={status.runs || []} 
              renderItem={item => (
                <List.Item className="run-item">
                  <div className="run-info">
                    <strong>参数:</strong> {JSON.stringify(item.params)}
                    <br />
                    <strong>Run ID:</strong> {item.run_id}
                  </div>
                </List.Item>
              )}
              className="runs-list"
            />
          </Card>
        )}
      </Card>
      
      {/* 内联样式定义 */}
      <style>
      {`
        .tuning-page {
          padding: 20px;
          min-height: 100vh;
          background-color: #f0f2f5;
        }
        
        .main-card {
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          overflow: hidden;
        }
        
        .card-title {
          display: flex;
          align-items: center;
          font-size: 18px;
          font-weight: 600;
        }
        
        .title-icon {
          margin-right: 8px;
        }
        
        .form-select {
          width: 100%;
          min-width: 200px;
        }
        
        .form-datepicker {
          width: 100%;
        }
        
        .params-section {
          margin-top: 24px;
        }
        
        .params-config-card {
          border: 1px solid #d9d9d9;
          border-radius: 6px;
          overflow: hidden;
        }
        
        .params-config-scrollable {
          max-height: 400px;
          overflow-y: auto;
          padding: 16px;
        }
        
        .params-config-scrollable::-webkit-scrollbar {
          width: 6px;
        }
        
        .params-config-scrollable::-webkit-scrollbar-track {
          background: #f1f1f1;
        }
        
        .params-config-scrollable::-webkit-scrollbar-thumb {
          background: #c1c1c1;
          border-radius: 3px;
        }
        
        .params-config-scrollable::-webkit-scrollbar-thumb:hover {
          background: #a8a8a8;
        }
        
        .param-row {
          padding: 8px 0;
          border-bottom: 1px solid #f0f0f0;
        }
        
        .param-row:last-child {
          border-bottom: none;
        }
        
        .param-name {
          font-weight: 600;
        }
        
        .param-name-text {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .param-value-select,
        .param-value-input,
        .param-range-input {
          width: 100%;
        }
        
        .empty-state-card {
          border: 1px dashed #d9d9d9;
          background-color: #fafafa;
          height: 200px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        
        .empty-state-content {
          text-align: center;
          color: #999;
        }
        
        .empty-state-icon {
          font-size: 48px;
          margin-bottom: 16px;
          color: #bfbfbf;
        }
        
        .action-section {
          margin-top: 24px;
          display: flex;
          justify-content: center;
          padding: 16px 0;
        }
        
        .run-button {
          padding: 0 32px;
          font-size: 16px;
        }
        
        .status-card {
          border-radius: 6px;
          margin-top: 24px !important;
        }
        
        .status-info {
          display: flex;
          flex-direction: column;
        }
        
        .status-label {
          font-size: 12px;
          color: #666;
          margin: 0;
          margin-bottom: 4px;
        }
        
        .status-value {
          font-size: 14px;
          font-weight: 500;
          margin: 0;
          word-break: break-all;
        }
        
        .status-progress {
          margin: 16px 0;
        }
        
        .runs-header {
          font-weight: 600;
          font-size: 14px;
          padding: 8px 0;
        }
        
        .runs-list {
          max-height: 200px;
          overflow-y: auto;
        }
        
        .run-item {
          padding: 8px 0;
          border-bottom: 1px solid #f0f0f0;
        }
        
        .run-item:last-child {
          border-bottom: none;
        }
        
        .run-info {
          word-break: break-all;
          font-size: 13px;
        }
        
        @media (max-width: 768px) {
          .tuning-page {
            padding: 12px;
          }
          
          .form-select {
            min-width: auto;
          }
        }
      `}
      </style>
    </div>
  );
}