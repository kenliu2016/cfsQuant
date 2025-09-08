
import { Layout, Tree, Card, Form, Input, DatePicker, Button, message, Modal } from 'antd'
import { useEffect, useState } from 'react'
import client from '../api/client'
import Editor from '@monaco-editor/react'
import dayjs from 'dayjs'

const { Sider, Content } = Layout

export default function StrategyPage(){
  const [form] = Form.useForm()
  const [tree, setTree] = useState<any[]>([])
  const [current, setCurrent] = useState<any | null>(null)
  const [code, setCode] = useState<string>('')
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')

  const load = async () => {
    const res = await client.get('/strategies')
    const rows = res.data.rows || []
    setTree(rows.map(r=>({ key: r.name, title: r.name })))
  }

  useEffect(() => { load() }, [])

  const onSelect = async (keys:any[]) => {
    if (!keys.length) return
    const name = keys[0]
    const res = await client.get('/strategies')
    const s = (res.data.rows || []).find((x:any)=>x.name===name)
    setCurrent(s || null)
    const codeRes = await client.get(`/strategies/${name}/code`)
    setCode(codeRes.data.code || '')
  }

  const onSaveCode = async () => {
    if (!current) return
    await client.post(`/strategies/${current.name}/code`, { code })
    message.success('已保存')
  }

  const onRun = async () => {
    const v = await form.validateFields()
    const payload = { code: v.code, start: v.range[0].format('YYYY-MM-DD HH:mm:ss'), end: v.range[1].format('YYYY-MM-DD HH:mm:ss'), strategy: current!.name, params: {} }
    const r = await client.post('/backtest', payload)
    if (r.data.backtest_id){
      message.success('回测完成')
    }
  }

  const onNew = async () => {
    if (!newName) return message.warn('请输入策略名')
    const r = await client.post('/api/strategies', { name: newName })
    if (r.data.status === 'ok') {
      message.success('已创建策略文件')
      setShowNew(false)
      setNewName('')
      load()
    } else if (r.data.status === 'exists') {
      message.warn('策略已存在')
    }
  }

  const onDelete = async () => {
    if (!current) return
    Modal.confirm({
      title: '确认删除策略',
      content: `将删除策略 ${current.name} 的文件（数据库记录请手动清理）。`,
      onOk: async ()=>{
        await client.delete(`/strategies/${current.name}`)
        message.success('已删除')
        setCurrent(null)
        setCode('')
        load()
      }
    })
  }

  const onUpload = async () => {
    if (!current) return
    await client.post(`/strategies/${current.name}/code`, { code })
    message.success('已上传/覆盖策略代码')
  }

  return (
    <Layout style={{ background:'#fff' }}>
      <Sider width={240} style={{ background:'#fff', borderRight:'1px solid #eee' }}>
        <Card size="small" title="策略树" bordered={false} bodyStyle={{padding:8}} extra={<Button size="small" onClick={()=>setShowNew(true)}>新建</Button>}>
          <Tree treeData={tree} onSelect={onSelect as any}/>
        </Card>
      </Sider>
      <Content style={{ padding: 16 }}>
        {current ? (
          <>
            <Card title={`策略: ${current.name}`} extra={<Button danger onClick={onDelete}>删除</Button>}>
              <Editor height="300px" defaultLanguage="python" value={code} onChange={(v)=>setCode(v||'')}/>
              <div style={{ marginTop: 8 }}>
                <Button type="primary" onClick={onSaveCode} style={{marginRight:8}}>保存</Button>
                <Button onClick={onUpload}>上传/覆盖</Button>
              </div>
            </Card>
            <Card style={{ marginTop: 16 }} title="回测">
              <Form form={form} layout="inline" initialValues={{ code: '000001.SZ', range: [dayjs().add(-7,'day'), dayjs()] }}>
                <Form.Item label="标的" name="code" rules={[{required:true}]}><Input style={{width:160}}/></Form.Item>
                <Form.Item label="区间" name="range" rules={[{required:true}]}><DatePicker.RangePicker showTime /></Form.Item>
                <Button type="primary" onClick={onRun}>启动回测</Button>
              </Form>
            </Card>
          </>
        ) : <Card>请选择左侧的策略</Card>}
      </Content>

      <Modal title="新建策略" open={showNew} onOk={onNew} onCancel={()=>setShowNew(false)}>
        <Input placeholder="策略名 (例如 demo2)" value={newName} onChange={(e)=>setNewName(e.target.value)} />
      </Modal>
    </Layout>
  )
}
