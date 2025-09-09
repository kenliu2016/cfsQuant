import { Card, Form, Input, DatePicker, Button, message, Tag, Select } from 'antd'
import client from '../api/client'
import dayjs from 'dayjs'
import { useState, useEffect, useCallback } from 'react'

export default function Monitor(){
  const [form] = Form.useForm()
  const [monitorId, setMonitorId] = useState<string | null>(null)
  const [status, setStatus] = useState<{status?: string, latest?: any, logs?: any[]} | null>(null)
  const [timer, setTimer] = useState<any>(null)
  const [symbols, setSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])

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

  useEffect(()=>{
    // 初始化时加载标的数据
    loadSymbols();
    return ()=> { if (timer) clearInterval(timer) } }, [timer])

  const onStart = async ()=>{
    const v = await form.validateFields()
    const r = await client.post('/monitor/start', { strategy: v.strategy, code: v.code, start: v.start.format('YYYY-MM-DD HH:mm:ss'), interval: v.interval || 10 })
    setMonitorId(r.data.monitor_id)
    message.success('监控已启动: ' + r.data.monitor_id)
    const t = setInterval(async ()=>{
      const s = await client.get('/monitor/' + r.data.monitor_id)
      setStatus(s.data)
    }, 2000)
    setTimer(t)
  }

  const onStop = async ()=>{
    if (!monitorId) return
    await client.post('/monitor/stop/' + monitorId)
    message.success('监控已停止')
    if (timer) clearInterval(timer)
    setTimer(null); setMonitorId(null)
  }

  return (<Card title='策略监控'>
    <Form form={form} layout="inline" initialValues={{ strategy:'demo', code:'BTCUSDT', start:dayjs().add(-1,'day'), interval:10 }}>
      <Form.Item label="策略" name="strategy" rules={[{required:true}]}><Input/></Form.Item>
      <Form.Item label="标的" name="code" rules={[{required:true}]}>
        <Select
          placeholder="请选择或输入标的"
          style={{width: 220}}
          showSearch
          filterOption={false}
          onSearch={handleSymbolSearch}
          options={filteredSymbols}
        />
      </Form.Item>
      <Form.Item label="开始时间" name="start" rules={[{required:true}]}><DatePicker showTime/></Form.Item>
      <Form.Item label="间隔(s)" name="interval"><Input/></Form.Item>
      <Button type="primary" onClick={onStart}>启动监控</Button>
      <Button danger onClick={onStop}>停止</Button>
    </Form>

    {status && (
      <div style={{marginTop:16}}>
        <div>Monitor ID: {monitorId}</div>
        <div>Latest: {status.latest ? JSON.stringify(status.latest) : <Tag>尚无信号</Tag>}</div>
        <div>Logs: <pre style={{maxHeight:200, overflow:'auto'}}>{JSON.stringify(status.logs ? status.logs.slice(-20) : [], null, 2)}</pre></div>
      </div>
    )}
  </Card>)
}
