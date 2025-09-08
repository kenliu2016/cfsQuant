import { Layout, Tree, Card, Form, Input, DatePicker, Button, message } from 'antd'
import { useEffect, useState } from 'react'
import client from '../api/client'
import Editor from '@monaco-editor/react'
import dayjs from 'dayjs'

const { Sider, Content } = Layout

type Strategy = {
  id: number
  name: string
  description?: string
  params: string
}

type ParamDef = {
  name: string
  label?: string
  type?: 'number' | 'text' | 'bool' | 'select'
  default?: any
  options?: { label: string; value: any }[]
}

export default function Backtest() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [selected, setSelected] = useState<Strategy | null>(null)
  const [form] = Form.useForm()
  const [code, setCode] = useState<string>('')

  useEffect(() => {
    client.get('/strategies').then((r) => setStrategies(r.data.rows || []))
  }, [])

  const onSelect = async (keys: any) => {
    const id = parseInt(keys[0])
    const s = strategies.find((x) => x.id === id) || null
    setSelected(s)
    if (s) {
      try {
        // 拉取代码
        const { data } = await client.get(`/strategies/${s.name}/code`)
        setCode(data.code || '')

        // 处理参数
        const ps: ParamDef[] = JSON.parse(s.params || '[]')
        const init: any = {}
        ps.forEach((p) => {
          if (p.default !== undefined) init[p.name] = p.default
        })
        form.setFieldsValue({
          strategy_id: s.id,
          strategy: s.name,
          code: '000001.SZ',
          start: dayjs().add(-5, 'day'),
          end: dayjs(),
          ...init,
        })
      } catch {
        form.resetFields()
      }
    }
  }

  const onRun = async () => {
    const v = await form.validateFields()
    const { data } = await client.post('/backtest', {
      code: v.code,
      start: v.start.format('YYYY-MM-DD HH:mm:ss'),
      end: v.end.format('YYYY-MM-DD HH:mm:ss'),
      strategy: v.strategy,
      params: { strategy_id: v.strategy_id, ...v },
    })
    if (data.backtest_id) message.success('回测完成: ' + data.backtest_id)
  }

  const onSave = async () => {
    if (!selected) return
    await client.post(`/strategies/${selected.name}/code`, { code })
    message.success('代码已保存')
  }

  return (
    <Layout style={{ height: '100%' }}>
      {/* 左侧策略树 */}
      <Sider width={260} style={{ background: '#fff', padding: '12px' }}>
        <Tree
          treeData={strategies.map((s) => ({
            key: s.id,
            title: `${s.id} · ${s.name}`,
          }))}
          onSelect={onSelect}
        />
      </Sider>

      {/* 右侧编辑区 */}
      <Content style={{ padding: '12px' }}>
        {selected ? (
          <>
            {/* 上半部分：策略代码编辑器 */}
            <Card
              title={`策略代码 — ${selected.name}`}
              style={{ marginBottom: 16 }}
              extra={<Button onClick={onSave}>保存代码</Button>}
            >
              <Editor
                height="300px"
                defaultLanguage="python"
                value={code}
                onChange={(val) => setCode(val || '')}
              />
            </Card>

            {/* 下半部分：参数 + 回测配置 */}
            <Card title="回测配置">
              <Form form={form} layout="vertical">
                <Form.Item name="strategy_id" label="策略ID">
                  <Input disabled />
                </Form.Item>
                <Form.Item name="strategy" label="策略代码">
                  <Input disabled />
                </Form.Item>
                <Form.Item name="code" label="标的代码" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
                <Form.Item name="start" label="开始时间" rules={[{ required: true }]}>
                  <DatePicker showTime />
                </Form.Item>
                <Form.Item name="end" label="结束时间" rules={[{ required: true }]}>
                  <DatePicker showTime />
                </Form.Item>
                <Button type="primary" onClick={onRun}>
                  启动回测
                </Button>
              </Form>
            </Card>
          </>
        ) : (
          <Card>请选择左侧的策略</Card>
        )}
      </Content>
    </Layout>
  )
}
