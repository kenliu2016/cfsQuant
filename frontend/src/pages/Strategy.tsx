
import { Layout, Tree, Card, Form, Input, DatePicker, Button, message, Modal, Row, Col } from 'antd'
import { useEffect, useState } from 'react'
import client from '../api/client'
import Editor from '@monaco-editor/react'
import dayjs from 'dayjs'

const { Content } = Layout

// 策略树组件
const StrategyTree = ({ onSelect, onCreate, onRefresh }: { onSelect: (strategy: any) => void, onCreate: () => void, onRefresh?: number }) => {
  const [tree, setTree] = useState<any[]>([])
  const [strategies, setStrategies] = useState<any[]>([])
  
  // 使用localStorage作为持久化缓存，设置缓存过期时间为5分钟
  const CACHE_KEY = 'strategies_cache'
  const CACHE_EXPIRE_TIME = 5 * 60 * 1000 // 5分钟

  const load = async () => {
    try {
      // 1. 首先尝试从localStorage读取缓存
      const cachedData = localStorage.getItem(CACHE_KEY)
      if (cachedData) {
        const { data, timestamp } = JSON.parse(cachedData)
        // 检查缓存是否过期
        if (Date.now() - timestamp < CACHE_EXPIRE_TIME) {
          setStrategies(data)
          setTree(data.map((r: {name: string, description?: string})=>({
            key: r.name, 
            title: (
              <div>
                <div style={{ fontWeight: 'bold' }}>{r.name}</div>
                {r.description && <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>{r.description}</div>}
              </div>
            )
          })))
          console.log('使用缓存的策略数据')
          return
        }
      }
      
      // 2. 缓存过期或不存在时，从API获取数据
      const res = await client.get('/strategies')
      const rows = res.data.rows || []
      setStrategies(rows)
      setTree(rows.map((r: {name: string, description?: string})=>({
        key: r.name, 
        title: (
          <div>
            <div style={{ fontWeight: 'bold' }}>{r.name}</div>
            {r.description && <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>{r.description}</div>}
          </div>
        )
      })))
      
      // 3. 将获取的数据存入缓存
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        data: rows,
        timestamp: Date.now()
      }))
      
    } catch (error) {
      console.error('加载策略树失败:', error)
      // 即使出错，也尝试显示缓存数据
      const cachedData = localStorage.getItem(CACHE_KEY)
      if (cachedData) {
        const { data } = JSON.parse(cachedData)
        setStrategies(data)
        setTree(data.map((r: {name: string, description?: string})=>({
          key: r.name, 
          title: (
            <div>
              <div style={{ fontWeight: 'bold' }}>{r.name}</div>
              {r.description && <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>{r.description}</div>}
            </div>
          )
        })))
      }
    }
  }

  useEffect(() => { load() }, [onRefresh])

  // 自定义onSelect处理函数，传递完整策略对象
  const handleSelect = (selectedKeys: any[]) => {
    if (!selectedKeys.length) return
    const name = selectedKeys[0]
    const strategy = strategies.find((s: any) => s.name === name)
    if (strategy) {
      onSelect(strategy)
    }
  }

  return (
    <Card 
      size="small" 
      title="策略管理" 
      variant="outlined" 
      styles={{body: {padding:8, height: '100%'}}} 
      extra={<Button size="small" onClick={onCreate}>新建</Button>}
    >
      <Tree treeData={tree} onSelect={handleSelect} />
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
    <Card title="回测设置" size="small" style={{ height: '100%' }} bodyStyle={{ padding: '8px', margin: 0 }}>
      <Form 
        form={form} 
        layout="vertical" 
        initialValues={{ code: 'BTCUSDT', range: [dayjs().add(-7,'day'), dayjs()] }}
        style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <Form.Item label="标的" name="code" rules={[{required:true}]} labelCol={{span:24}}>
            <Input style={{width: '100%', maxWidth: '200px'}}/>
          </Form.Item>
          <Form.Item label="区间" name="range" rules={[{required:true}]} labelCol={{span:24}}>
            <DatePicker.RangePicker showTime size="small" style={{width: '100%'}} />
          </Form.Item>
        </div>
        <div style={{ marginTop: '4px' }}>
          <Button type="primary" onClick={onRun} style={{ width: '50%' }} size="middle">开始回测</Button>
        </div>
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
    // 清除localStorage中的策略缓存
    localStorage.removeItem('strategies_cache')
    setRefreshTrigger(prev => prev + 1)
  }

  const onSelect = async (strategy:any) => {
    if (!strategy) return
    setCurrent(strategy)
    const codeRes = await client.get(`/strategies/${strategy.name}/code`)
    setCode(codeRes.data.code || '')
  }

  const onSaveCode = async () => {
    if (!current) return
    await client.post(`/strategies/${current.name}/code`, { code })
    message.success('已保存')
    // 触发策略树刷新
    refreshStrategyTree()
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
        
        // 直接使用创建的策略信息设置当前选中，无需等待刷新后再查询
        const newStrategy = {
          name: newName,
          description: newDescription
        };
        setCurrent(newStrategy);
        
        // 获取新策略的代码（默认为空）
        try {
          const codeRes = await client.get(`/strategies/${newName}/code`)
          setCode(codeRes.data?.code || '')
        } catch (error) {
          console.error('获取策略代码失败:', error)
          setCode('')
        }
        
        // 触发策略树刷新，但不需要等待刷新完成再选择策略
        refreshStrategyTree()
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
        // 触发策略树刷新
        refreshStrategyTree()
      }
    })
  }

  return (
    <Layout style={{ background:'#fff', height: '100vh' }}>
      <Content style={{ padding: 16, height: '100%' }}>
        {/* 左右结构 */}
        <Row gutter={[16, 0]} style={{ height: '100%' }}>
          {/* 左侧列 */}
          <Col span={6} style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* 左上：策略树 */}
            <div style={{ height: '64%' }}>
              <StrategyTree onSelect={onSelect} onCreate={() => setShowNew(true)} onRefresh={refreshTrigger} />
            </div>
            {/* 左下：执行参数和按钮 */}
            <div style={{ height: '36%' }}>
              <UserOperationPanel form={form} current={current} onRun={onRun} />
            </div>
          </Col>
          {/* 右侧：代码编辑区 */}
          <Col span={18} style={{ height: '100%' }}>
            <CodeEditor 
              current={current} 
              code={code} 
              onCodeChange={setCode} 
              onSave={onSaveCode} 
              onDelete={onDelete} 
            />
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
