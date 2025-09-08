
import { Layout, Tree, Card, Form, Input, DatePicker, Button, message, Modal, Row, Col } from 'antd'
import { useEffect, useState } from 'react'
import client from '../api/client'
import Editor from '@monaco-editor/react'
import dayjs from 'dayjs'

const { Content } = Layout

// 策略树组件
const StrategyTree = ({ onSelect, onCreate, onRefresh }: { onSelect: (keys: any[]) => void, onCreate: () => void, onRefresh?: number }) => {
  const [tree, setTree] = useState<any[]>([])

  const load = async () => {
    const res = await client.get('/strategies')
    const rows = res.data.rows || []
    setTree(rows.map((r: {name: string, description?: string})=>({
      key: r.name, 
      title: (
        <div>
          <div style={{ fontWeight: 'bold' }}>{r.name}</div>
          {r.description && <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>{r.description}</div>}
        </div>
      )
    })))
  }

  useEffect(() => { load() }, [onRefresh])

  return (
    <Card 
      size="small" 
      title="策略树" 
      variant="outlined" 
      styles={{body: {padding:8, height: '100%'}}} 
      extra={<Button size="small" onClick={onCreate}>新建</Button>}
    >
      <Tree treeData={tree} onSelect={onSelect} />
    </Card>
  )
}

// 代码编辑器组件
const CodeEditor = ({ current, code, onCodeChange, onSave, onDelete }: any) => {
  if (!current) {
    return <Card style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      请选择左侧的策略
    </Card>
  }

  return (
    <Card 
      title={`策略: ${current.name}`} 
      extra={
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button type="primary" onClick={onSave}>保存</Button>
          <Button onClick={onSave}>上传/覆盖</Button>
          <Button danger onClick={onDelete}>删除</Button>
        </div>
      }
      style={{ height: '100%' }}
      bodyStyle={{ height: 'calc(100% - 50px)', padding: 0, overflow: 'hidden' }}
    >
      <Editor 
        height="100%" 
        defaultLanguage="python" 
        value={code} 
        onChange={(v)=>onCodeChange(v||'')}
      />
    </Card>
  )
}

// 用户操作区组件
const UserOperationPanel = ({ form, current, onRun }: any) => {
  if (!current) {
    return <Card style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      请选择策略后进行操作
    </Card>
  }

  return (
    <Card title="回测与操作" style={{ height: '100%' }}>
      <Form 
        form={form} 
        layout="inline" 
        initialValues={{ code: 'BTCUSDT', range: [dayjs().add(-7,'day'), dayjs()] }}
      >
        <Form.Item label="标的" name="code" rules={[{required:true}]}>
          <Input style={{width:160}}/>
        </Form.Item>
        <Form.Item label="区间" name="range" rules={[{required:true}]}>
          <DatePicker.RangePicker showTime />
        </Form.Item>
        <Button type="primary" onClick={onRun}>启动回测</Button>
      </Form>
    </Card>
  )
}

export default function StrategyPage(){
  const [form] = Form.useForm()
  const [current, setCurrent] = useState<any | null>(null)
  const [code, setCode] = useState<string>('')
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  
  const refreshStrategyTree = () => {
    setRefreshTrigger(prev => prev + 1)
  }

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
    if (!newName) return message.warning('请输入策略名')
    try {
      const r = await client.post('/strategies', { name: newName, description: newDescription })
      if (r.data && r.data.status === 'ok') {
        message.success('已创建策略文件')
        setShowNew(false)
        setNewName('')
        setNewDescription('')
        
        // 触发策略树刷新
        refreshStrategyTree()
        
        // 选择新创建的策略
        setTimeout(async () => {
          try {
            const res = await client.get('/strategies')
            const rows = res.data?.rows || []
            const s = rows.find((x:any)=>x.name===newName)
            if (s) {
              setCurrent(s)
              const codeRes = await client.get(`/strategies/${newName}/code`)
              setCode(codeRes.data?.code || '')
            }
          } catch (error) {
            console.error('选择新策略失败:', error)
          }
        }, 100)
      } else if (r.data && r.data.status === 'exists') {
        message.warning('策略已存在')
      } else {
        message.error('创建失败: 未知的响应状态')
        // 即使响应不符合预期，也关闭窗口
        setShowNew(false)
      }
    } catch (error) {
      console.error('创建策略失败:', error)
      message.error('创建策略时发生错误')
      // 发生异常时也确保关闭窗口
      setShowNew(false)
    }
  }

  const onDelete = async () => {
    if (!current) return
    Modal.confirm({
      title: '确认删除策略',
      content: `将删除策略 ${current.name} 的文件及其数据库记录。`,
      onOk: async ()=>{
        await client.delete(`/strategies/${current.name}`)
        message.success('已删除')
        setCurrent(null)
        setCode('')
      }
    })
  }

  return (
    <Layout style={{ background:'#fff', height: '100vh' }}>
      <Content style={{ padding: 16, height: '100%' }}>
        {/* 上半部分：策略树和代码编辑器 */}
        <Row gutter={[16, 16]} style={{ height: 'calc(80% - 8px)' }}>
          <Col span={6}>
            <StrategyTree onSelect={onSelect} onCreate={() => setShowNew(true)} onRefresh={refreshTrigger} />
          </Col>
          <Col span={18}>
            <CodeEditor 
              current={current} 
              code={code} 
              onCodeChange={setCode} 
              onSave={onSaveCode} 
              onDelete={onDelete} 
            />
          </Col>
        </Row>
        
        {/* 下半部分：用户操作区 */}
        <Row style={{ height: 'calc(20% - 8px)' }}>
          <Col span={24}>
            <UserOperationPanel form={form} current={current} onRun={onRun} />
          </Col>
        </Row>
      </Content>

      <Modal title="新建策略" open={showNew} onOk={onNew} onCancel={()=>setShowNew(false)}>
        <div style={{marginBottom: 12}}>
          <Input placeholder="策略名 (例如 demo2)" value={newName} onChange={(e)=>setNewName(e.target.value)} />
        </div>
        <Input.TextArea placeholder="策略描述" value={newDescription} onChange={(e)=>setNewDescription(e.target.value)} rows={4} />
      </Modal>
    </Layout>
  )
}
