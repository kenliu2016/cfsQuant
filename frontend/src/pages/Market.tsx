
import React, { useEffect, useState } from 'react'
import { Card, Form, Input, DatePicker, Button, Tabs } from 'antd'
import client from '../api/client'
import dayjs from 'dayjs'
import ReactECharts from 'echarts-for-react'

const { RangePicker } = DatePicker

type Row = { datetime: string; open:number; high:number; low:number; close:number; volume:number }

export default function Market() {
  const [form] = Form.useForm()
  const [daily, setDaily] = useState<Row[]>([])
  const [intraday, setIntraday] = useState<Row[]>([])

  useEffect(() => {
    const today = dayjs().startOf('day')
    form.setFieldsValue({
      code: '000001.SZ',
      dailyRange: [today.add(-6,'day').hour(0).minute(0), today.hour(23).minute(59)],
      intradayRange: [today, today.endOf('day')]
    })
  }, [])

  const fetchDaily = async () => {
    const v = await form.validateFields()
    const [start, end] = v.dailyRange
    const res = await client.get('/market/daily', { params: { code: v.code, start: start.format('YYYY-MM-DD HH:mm:ss'), end: end.format('YYYY-MM-DD HH:mm:ss') } })
    setDaily(res.data.rows || [])
  }

  const fetchIntraday = async () => {
    const v = await form.validateFields()
    const [start, end] = v.intradayRange
    const res = await client.get('/market/intraday', { params: { code: v.code, start: start.format('YYYY-MM-DD HH:mm:ss'), end: end.format('YYYY-MM-DD HH:mm:ss') } })
    setIntraday(res.data.rows || [])
  }

  const candleOption = {
    tooltip: { trigger: 'axis' },
    axisPointer: { type: 'cross' },
    xAxis: [{ type: 'category', data: daily.map(r=>r.datetime), scale:true }, { type:'category', gridIndex:1, data: daily.map(r=>r.datetime), axisLabel:{show:false} }],
    yAxis: [{ scale:true }, { gridIndex:1 }],
    grid:[{ left:40, right:20, height: '60%' }, { left:40, right:20, top: '70%', height: '20%' }],
    series: [
      { type:'candlestick', name:'K', data: daily.map(r=>[r.open,r.close,r.low,r.high]) },
      { type:'bar', name:'Volume', xAxisIndex:1, yAxisIndex:1, data: daily.map(r=>r.volume) }
    ]
  }

  const lineOption = {
    tooltip: { trigger: 'axis' },
    xAxis: [{ type: 'category', data: intraday.map(r=>r.datetime) }, { type:'category', gridIndex:1, data: intraday.map(r=>r.datetime), axisLabel:{show:false} }],
    yAxis: [{}, { gridIndex:1 }],
    grid:[{ left:40, right:20, height: '60%' }, { left:40, right:20, top: '70%', height: '20%' }],
    series: [
      { type:'line', name:'Price', data: intraday.map(r=>r.close), showSymbol:false, smooth:true },
      { type:'bar', name:'Volume', xAxisIndex:1, yAxisIndex:1, data: intraday.map(r=>r.volume) }
    ]
  }

  return (
    <Card title="Market 行情">
      <Form form={form} layout="inline">
        <Form.Item name="code" label="标的" rules={[{required:true}]}><Input placeholder="e.g. 000001.SZ" style={{width:160}}/></Form.Item>
        <Form.Item name="dailyRange" label="日线区间" rules={[{required:true}]}><RangePicker showTime /></Form.Item>
        <Form.Item><Button onClick={fetchDaily} type="primary">加载日线</Button></Form.Item>
        <Form.Item name="intradayRange" label="实时区间" rules={[{required:true}]}><RangePicker showTime /></Form.Item>
        <Form.Item><Button onClick={fetchIntraday}>加载实时</Button></Form.Item>
      </Form>

      <div style={{ marginTop: 16 }}>
        <Tabs items={[
          { key:'daily', label:'日线(K线+量)', children:<ReactECharts option={candleOption} style={{height: 500}}/> },
          { key:'rt', label:'实时(折线+量)', children:<ReactECharts option={lineOption} style={{height: 500}}/> }
        ]} />
      </div>
    </Card>
  )
}
