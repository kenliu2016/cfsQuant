import { Card, Form, Input, DatePicker, Button, message, Progress, List } from 'antd'
import client from '../api/client'
import dayjs from 'dayjs'
import { useState, useEffect } from 'react'

export default function Tuning(){
  const [form] = Form.useForm()
  const [task, setTask] = useState<string | null>(null)
  const [status, setStatus] = useState<{status?: string, total?: number, finished?: number, runs?: any[]} | null>(null)
  const [timer, setTimer] = useState<any>(null)

  useEffect(()=>{
    return ()=> { if (timer) clearInterval(timer) }
  },[timer])

  const onRun = async () => {
    const v = await form.validateFields()
    const payload = { strategy: v.strategy, params: JSON.parse(v.params || '{}'), code: v.code, start: v.range[0].format('YYYY-MM-DD HH:mm:ss'), end: v.range[1].format('YYYY-MM-DD HH:mm:ss') }
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

  return (<Card title='参数寻优'>
    <Form form={form} layout="vertical" initialValues={{ strategy:'demo', code:'000001.SZ', range:[dayjs().add(-30,'day'), dayjs()] }}>
      <Form.Item label="策略" name="strategy" rules={[{required:true}]}><Input/></Form.Item>
      <Form.Item label="标的" name="code" rules={[{required:true}]}><Input/></Form.Item>
      <Form.Item label="区间" name="range" rules={[{required:true}]}><DatePicker.RangePicker showTime/></Form.Item>
      <Form.Item label="参数范围(JSON)" name="params" tooltip="例如: {'short':[5,10], 'long':[20,30]}"><Input.TextArea rows={4}/></Form.Item>
      <Button type="primary" onClick={onRun}>开始寻优</Button>
    </Form>

    {status && (
      <div style={{marginTop:16}}>
        <div>任务: {task}</div>
        <div>状态: {status.status}</div>
        <Progress percent={ status.total && status.finished ? Math.round((status.finished/status.total)*100) : 0 } />
        <List size="small" header={<div>已完成组合</div>} dataSource={status.runs || []} renderItem={item=> (<List.Item>{JSON.stringify(item)}</List.Item>)} style={{maxHeight:200, overflow:'auto'}} />
      </div>
    )}
  </Card>)
}
