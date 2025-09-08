
import { Card, Table, Button, Space, message, Checkbox, Select } from 'antd'
import { useEffect, useState } from 'react'
import client from '../api/client'
import ReactECharts from 'echarts-for-react'

export default function Reports(){
  const [runs, setRuns] = useState<any[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [compareData, setCompareData] = useState<any[]>([])
  const [sortMetric, setSortMetric] = useState<string>('sharpe')

  useEffect(()=>{ loadRuns() },[])

  const loadRuns = async ()=>{
    const res = await client.get('/runs?limit=200')
    setRuns(res.data.rows || [])
  }

  const onExport = async (id:string)=>{
    const r = await client.get(`/runs/${id}`)
    message.info('已加载结果')
  }

  const onCompare = async ()=>{
    if (selected.length < 2) return message.warn('请选择至少2个回测进行对比')
    const all = []
    for (const id of selected){
      const r = await client.get(`/backtest/${id}/results`)
      const metrics = r.data.metrics || []
      const mobj:any = {}
      metrics.forEach((m:any)=> mobj[m.metric_name]=m.metric_value)
      all.push({ id, metrics: mobj })
    }
    // sort by selected metric descending
    all.sort((a,b)=> (b.metrics[sortMetric]||0) - (a.metrics[sortMetric]||0))
    setCompareData(all)
  }

  const columns = [
    { title:'Run ID', dataIndex:'run_id', key:'run_id' },
    { title:'Strategy', dataIndex:'strategy', key:'strategy' },
    { title:'Code', dataIndex:'code', key:'code' },
    { title:'Start', dataIndex:'start', key:'start' },
    { title:'End', dataIndex:'end', key:'end' },
    { title:'Initial', dataIndex:'initial_capital', key:'initial_capital' },
    { title:'Final', dataIndex:'final_capital', key:'final_capital' }
  ]

  return (<Card title='Reports'>
    <Space style={{marginBottom:12}}>
      <Select value={sortMetric} onChange={(v)=>setSortMetric(v)} style={{width:160}}>
        <Select.Option value="sharpe">Sharpe</Select.Option>
        <Select.Option value="total_return">Total Return</Select.Option>
        <Select.Option value="max_drawdown">Max Drawdown</Select.Option>
      </Select>
      <Button onClick={onCompare}>比较所选</Button>
      <Button onClick={loadRuns}>刷新</Button>
    </Space>
    <Table rowKey="run_id" dataSource={runs} columns={columns} rowSelection={{
      selectedRowKeys: selected,
      onChange: (keys)=> setSelected(keys as string[])
    }} pagination={{pageSize:20}} />

    {compareData.length>0 && (
      <Card title="比较结果" style={{marginTop:16}}>
        <Table dataSource={compareData} rowKey="id" columns={[
          {title:'Run', dataIndex:'id', key:'id'},
          {title:'Sharpe', dataIndex:['metrics','sharpe'], key:'sharpe', render:(_,r)=> r.metrics.sharpe},
          {title:'Total Return', dataIndex:['metrics','total_return'], key:'total_return', render:(_,r)=> r.metrics.total_return},
          {title:'Max Drawdown', dataIndex:['metrics','max_drawdown'], key:'max_drawdown', render:(_,r)=> r.metrics.max_drawdown}
        ]} pagination={false} />
      </Card>
    )}
  </Card>)
}
