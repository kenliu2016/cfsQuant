import client from '../api/client'
import dayjs from 'dayjs'
import { useState, useEffect, useCallback } from 'react'
import { Form } from 'antd'
import { Select } from 'antd'
import { InputNumber } from 'antd'
import { Button } from 'antd'
import { Divider } from 'antd'
import { Card } from 'antd'
import { List } from 'antd'
import { Progress } from 'antd'
import { Input } from 'antd'
import { Row } from 'antd'
import { Col } from 'antd'
import { message } from 'antd'
import { DatePicker } from 'antd'

// 定义参数配置类型
interface ParamConfig {
  default: any;
  min?: number;
  max?: number;
  step?: number;
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

export default function Tuning(){
  const [form] = Form.useForm()
  const [task, setTask] = useState<string | null>(null)
  const [status, setStatus] = useState<{status?: string, total?: number, finished?: number, runs?: any[]} | null>(null)
  const [timer, setTimer] = useState<any>(null)
  const [symbols, setSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])
  const [strategies, setStrategies] = useState<{ value: string; label: string }[]>([])
  const [filteredStrategies, setFilteredStrategies] = useState<{ value: string; label: string }[]>([])
  const [strategyParams, setStrategyParams] = useState<{[key: string]: ParamConfig}>({})

  // 解析CSV文件加载标的数据
  const loadSymbols = async () => {
    try {
      const response = await fetch('/src/assets/symbols.csv');
      const csvText = await response.text();
      
      // 解析CSV
      const lines = csvText.trim().split('\n');
      const headers = lines[0].split(',').map(h => h.trim());
      
      const symbolData = [];
      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',');
        const symbolObj = headers.reduce((obj, header, index) => {
          obj[header] = values[index]?.trim();
          return obj;
        }, {} as any);
        
        // 将code和name格式化为Select组件需要的格式
        symbolData.push({
          value: symbolObj.code,
          label: `${symbolObj.code} - ${symbolObj.name}`
        });
      }
      
      setSymbols(symbolData);
      setFilteredSymbols(symbolData);
    } catch (error) {
      console.error('加载标的数据失败:', error);
    }
  }
  
  // 加载策略列表
  const loadStrategies = async () => {
    try {
      const response = await client.get('/strategies');
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
      const response = await client.get('/strategies');
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
              default: value
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
    
    const payload = { 
      strategy: v.strategy, 
      params: paramsGrid, 
      code: v.code, 
      start: v.range[0].format('YYYY-MM-DD HH:mm:ss'), 
      end: v.range[1].format('YYYY-MM-DD HH:mm:ss') 
    };
    
    const r = await client.post('/tuning', payload)
    const task_id = r.data.task_id
    setTask(task_id)
    message.success('任务已提交: ' + task_id)
    // start polling
    const t = setInterval(async ()=>{
      const s = await client.get('/tuning/' + task_id)
      setStatus(s.data)
      if (s.data && s.data.status && s.data.status !== 'pending') {
        clearInterval(t); setTimer(null)
      }
    }, 2000)
    setTimer(t)
  }

  // 渲染参数设置表单
  const renderParamSettings = () => {
    if (Object.keys(strategyParams).length === 0) {
      return <div>请先选择策略</div>;
    }
    
    return (
      <div style={{maxHeight: 400, overflowY: 'auto'}}>
        {Object.entries(strategyParams).map(([key, param]) => (
          <div key={key} style={{marginBottom: 8, display: 'flex', alignItems: 'center'}}>
            <div style={{fontWeight: 'bold', width: 120, paddingRight: 8}}>{key}</div>
            
            <Form.Item
              name={['paramsConfig', key, 'currentValue']}
              initialValue={param.default}
              style={{margin: '0 8px', width: 80}}
            >
              <InputNumber style={{width: '100%'}} placeholder="值" />
            </Form.Item>
            
            <Form.Item
              name={['paramsConfig', key, 'min']}
              style={{margin: '0 8px', width: 80}}
            >
              <InputNumber min={0} style={{width: '100%'}} placeholder="最小" />
            </Form.Item>
            
            <Form.Item
              name={['paramsConfig', key, 'max']}
              style={{margin: '0 8px', width: 80}}
            >
              <InputNumber min={0} style={{width: '100%'}} placeholder="最大" />
            </Form.Item>
            
            <Form.Item
              name={['paramsConfig', key, 'step']}
              style={{margin: '0 8px', width: 80}}
            >
              <InputNumber min={0.0001} style={{width: '100%'}} placeholder="步长" />
            </Form.Item>
            
            <Form.Item
              name={['paramsConfig', key, 'type']}
              initialValue="range"
              hidden
            >
              <Input />
            </Form.Item>
          </div>
        ))}
      </div>
    );
  };
  
  return (
    <Card title='参数寻优'>
      <Form form={form} layout="vertical" initialValues={{ 
        code: 'BTCUSDT', 
        range: [dayjs().add(-30, 'day'), dayjs()],
        paramsConfig: {}
      }}>
        <Form.Item label="策略" name="strategy" rules={[{required: true}]}>
          <Select
            placeholder="请选择策略"
            style={{width: 220}}
            showSearch
            filterOption={false}
            onSearch={handleStrategySearch}
            onChange={handleStrategyChange}
            options={filteredStrategies}
          />
        </Form.Item>
        <Form.Item label="标的" name="code" rules={[{required: true}]}>
          <Select
            placeholder="请选择或输入标的"
            style={{width: 220}}
            showSearch
            filterOption={false}
            onSearch={handleSymbolSearch}
            options={filteredSymbols}
          />
        </Form.Item>
        <Form.Item label="区间" name="range" rules={[{required: true}]}>
          <DatePicker.RangePicker showTime />
        </Form.Item>
        
        <Divider>参数范围设置</Divider>
        {renderParamSettings()}
        
        <Button 
          type="primary" 
          onClick={onRun}
          disabled={Object.keys(strategyParams).length === 0}
          style={{marginTop: 16}}
        >
          开始寻优
        </Button>
      </Form>

      {status && (
        <div style={{marginTop: 16}}>
          <div>任务: {task}</div>
          <div>状态: {status.status}</div>
          <Progress percent={status.total && status.finished ? Math.round((status.finished / status.total) * 100) : 0} />
          <List 
            size="small" 
            header={<div>已完成组合</div>} 
            dataSource={status.runs || []} 
            renderItem={item => (
              <List.Item>
                <div>
                  <strong>参数:</strong> {JSON.stringify(item.params)}
                  <br />
                  <strong>Run ID:</strong> {item.run_id}
                </div>
              </List.Item>
            )}
            style={{maxHeight: 200, overflow: 'auto'}} 
          />
        </div>
      )}
    </Card>
  );
}