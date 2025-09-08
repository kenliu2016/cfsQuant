import { Card, Form, Input, DatePicker, Button, message, Tag } from 'antd'
import client from '../api/client'
import dayjs from 'dayjs'
import { useState, useEffect } from 'react'

export default function Monitor(){
  const [form] = Form.useForm()
  const [monitorId, setMonitorId] = useState<string | null>(null)
  const [status, setStatus] = useState<{status?: string, latest?: any, logs?: any[]} | null>(null)
  const [timer, setTimer] = useState<any>(null)

  useEffect(()=>{ return ()=> { if (timer) clearInterval(timer) } }, [timer])

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
    <Form form={form} layout="inline" initialValues={{ strategy:'demo', code:'000001.SZ', start:dayjs().add(-1,'day'), interval:10 }}>
      <Form.Item label="策略" name="strategy" rules={[{required:true}]}><Input/></Form.Item>
      <Form.Item label="标的" name="code" rules={[{required:true}]}><Input/></Form.Item>
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
