
import { Card, Table, Button, Space, message, Select, Modal, Tabs, Statistic } from 'antd'
import { useEffect, useState, useMemo } from 'react'
import client from '../api/client'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import * as XLSX from 'xlsx'

// 格式化日期时间函数
const formatDateTime = (dateString: string) => {
  if (!dateString) return ''
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

const Reports = () => {
  const [runs, setRuns] = useState<any[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [compareData, setCompareData] = useState<any[]>([])
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [currentRunDetail, setCurrentRunDetail] = useState<any>({})
  const [currentRunEquity, setCurrentRunEquity] = useState<any[]>([])
  const [currentRunTrades, setCurrentRunTrades] = useState<any[]>([])
  const [searchText, setSearchText] = useState<string>('')
  const [strategySearchText, setStrategySearchText] = useState<string>('')
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredStrategies, setFilteredStrategies] = useState<{ value: string; label: string }[]>([])
  const [sortMetric] = useState('sharpe')
  const [currentRunKlineData, setCurrentRunKlineData] = useState<any[]>([])

  // 加载回测列表
  const loadRuns = async () => {
    try {
      const res = await client.get('/runs')
      setRuns(res.data.rows || [])
      
      // 提取唯一的标的和策略
      const symbols: string[] = Array.from(new Set(res.data.rows.map((run: any) => run.code)))
      const strategies: string[] = Array.from(new Set(res.data.rows.map((run: any) => run.strategy)))
      
      setFilteredSymbols(symbols.map((s) => ({ value: s, label: s })))
      setFilteredStrategies(strategies.map((s) => ({ value: s, label: s })))
    } catch (error) {
      console.error('加载回测列表失败:', error)
      message.error('加载回测列表失败')
    }
  }

  // 加载回测详情
  const loadRunDetail = async (runId: string) => {
    try {
      const res = await client.get(`/runs/${runId}`)
      setCurrentRunDetail(res.data.info || {})
      setCurrentRunEquity(res.data.equity || [])
      setCurrentRunTrades(res.data.trades || [])
      setDetailModalVisible(true)
      
      // 同时加载K线数据
      if (res.data.info && res.data.info.code) {
        await loadKlineData(res.data.info.code, res.data.info.start_time, res.data.info.end_time)
      }
    } catch (error) {
      console.error('加载回测详情失败:', error)
      message.error('加载回测详情失败')
    }
  }

  // 加载K线数据（分时图）
  const loadKlineData = async (code: string, startTime: string, endTime: string) => {
    try {
      const res = await client.get('/market/intraday', {
        params: {
          code: code,
          start: startTime,
          end: endTime
        }
      })
      setCurrentRunKlineData(res.data.rows || [])
    } catch (error) {
      console.error('加载K线数据失败:', error)
    }
  }

  // 关闭详情弹窗
  const handleCloseDetailModal = () => {
    setDetailModalVisible(false)
  }

  // 准备收益曲线数据
  const prepareEquityChartData = useMemo(() => {
    if (!currentRunEquity || currentRunEquity.length === 0) {
      return null
    }

    const dates = currentRunEquity.map(item => dayjs(item.datetime).format('YYYY-MM-DD HH:mm'))
    const nav = currentRunEquity.map(item => item.nav)
    const drawdown = currentRunEquity.map(item => item.drawdown)

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          let result = `${params[0].axisValue}<br/>`
          params.forEach(param => {
            result += `${param.seriesName}: ${param.value}<br/>`
          })
          return result
        }
      },
      legend: {
        data: ['净值', '回撤']
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: {
          interval: Math.floor(dates.length / 10), // 控制显示的标签数量
          rotate: 45
        }
      },
      yAxis: [
        {
          type: 'value',
          name: '净值',
          position: 'left'
        },
        {
          type: 'value',
          name: '回撤',
          position: 'right',
          axisLabel: {
            formatter: '{value}%'
          }
        }
      ],
      series: [
        {
          name: '净值',
          type: 'line',
          data: nav,
          smooth: true,
          yAxisIndex: 0
        },
        {
          name: '回撤',
          type: 'line',
          data: drawdown,
          smooth: true,
          yAxisIndex: 1,
          lineStyle: {
            color: '#f5222d'
          }
        }
      ]
    }
  }, [currentRunEquity])

  // 准备带有买卖点的K线图数据
  const prepareKlineWithTradesData = useMemo(() => {
    if (!currentRunKlineData || currentRunKlineData.length === 0) {
      return null
    }

    const dateTimes: string[] = []
    const candlestickData: number[][] = []
    const volumeData: number[] = []
    const buyPoints: any[] = []
    const sellPoints: any[] = []

    // 处理K线数据
    for (let i = 0; i < currentRunKlineData.length; i++) {
      const row = currentRunKlineData[i]
      dateTimes.push(row.datetime)
      candlestickData.push([row.open, row.close, row.low, row.high])
      volumeData.push(row.volume)
    }

    // 处理交易点数据
    if (currentRunTrades && currentRunTrades.length > 0) {
      for (let i = 0; i < currentRunTrades.length; i++) {
        const trade = currentRunTrades[i]
        const index = dateTimes.indexOf(trade.datetime)
        
        if (index !== -1) {
          if (trade.side === 'buy') {
            buyPoints.push({
              name: '买入',
              value: [index, trade.price],
              itemStyle: {
                color: '#52c41a' // 绿色表示买入
              }
            })
          } else if (trade.side === 'sell') {
            sellPoints.push({
              name: '卖出',
              value: [index, trade.price],
              itemStyle: {
                color: '#f5222d' // 红色表示卖出
              }
            })
          }
        }
      }
    }

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        },
        formatter: (params: any[]) => {
          let result = `${dayjs(dateTimes[params[0].axisValue]).format('YYYY-MM-DD HH:mm')}<br/>`
          params.forEach(param => {
            if (param.seriesType === 'candlestick') {
              result += `开: ${param.data[0]}<br/>`
              result += `收: ${param.data[1]}<br/>`
              result += `低: ${param.data[2]}<br/>`
              result += `高: ${param.data[3]}<br/>`
            } else if (param.seriesType === 'scatter') {
              result += `${param.seriesName}: ${param.value[1]}<br/>`
              // 查找对应的交易详情
              const tradeIndex = dateTimes.indexOf(dateTimes[param.value[0]])
              if (tradeIndex !== -1) {
                const trade = currentRunTrades.find(t => t.datetime === dateTimes[tradeIndex])
                if (trade) {
                  result += `数量: ${Math.abs(trade.qty)}<br/>`
                  if (trade.realized_pnl !== null && trade.realized_pnl !== undefined) {
                    result += `盈亏: ${trade.realized_pnl.toFixed(2)}<br/>`
                  }
                }
              }
            }
          })
          return result
        }
      },
      legend: {
        data: ['K线', '买入', '卖出']
      },
      xAxis: [
        {
          type: 'category', 
          data: dateTimes,
          scale: true,
          axisLabel: {
            formatter: (value: string) => {
              return dayjs(value).format('MM-DD');
            },
            show: true,
            color: '#333',
            rotate: 45,
            interval: (_index: number) => {
              const totalPoints = dateTimes.length;
              if (totalPoints === 0) return false;
              if (totalPoints <= 10) return 0;
              if (totalPoints <= 30) return Math.floor(totalPoints / 10);
              if (totalPoints <= 60) return Math.floor(totalPoints / 20);
              return Math.floor(totalPoints / 30);
            }
          },
          axisLine: { show: true },
          axisTick: { show: true }
        },
        {
          type:'category',
          gridIndex:1,
          data: dateTimes,
          axisLabel:{show:false}
        }
      ],
      yAxis: [
        {
          type: 'value',
          scale: true,
          axisLabel: {
            formatter: (value: number) => {
              if (value >= 1000000) {
                return Math.round(value / 1000000) + 'M';
              } else if (value >= 1000) {
                return Math.round(value / 1000) + 'K';
              } else {
                return Math.round(value).toString();
              }
            },
            interval: 'auto'
          }
        },
        {
          gridIndex:1,
          axisLabel: {
            formatter: (value: number) => {
              if (value >= 1000000) {
                return Math.round(value / 1000000) + 'M';
              } else if (value >= 1000) {
                return Math.round(value / 1000) + 'K';
              } else {
                return Math.round(value).toString();
              }
            },
            interval: 'auto'
          }
        }
      ],
      grid:[{ left:40, right:20, height: '55%' }, { left:40, right:20, top: '65%', height: '20%' }],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: candlestickData
        },
        {
          name: '买入',
          type: 'scatter',
          data: buyPoints,
          symbolSize: 15,
          symbol: 'triangle',
          itemStyle: {
            color: '#52c41a'
          }
        },
        {
          name: '卖出',
          type: 'scatter',
          data: sellPoints,
          symbolSize: 15,
          symbol: 'triangleDown',
          itemStyle: {
            color: '#f5222d'
          }
        },
        {
          type: 'bar',
          name: '成交量',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumeData,
          itemStyle: {
            color: (params: any) => {
              // 根据收盘价与开盘价的关系设置成交量柱子颜色
              const open = candlestickData[params.dataIndex][0]
              const close = candlestickData[params.dataIndex][1]
              return close >= open ? '#52c41a' : '#f5222d'
            }
          }
        }
      ]
    }
  }, [currentRunKlineData, currentRunTrades])

  // 标的搜索处理
  const handleSymbolSearch = async (value: string) => {
    // 这里可以实现异步搜索，现在简单处理
    const filtered = filteredSymbols.filter(option => 
      option.label.toLowerCase().includes(value.toLowerCase())
    );
    setFilteredSymbols(filtered);
  }

  // 策略搜索处理
  const handleStrategySearch = async (value: string) => {
    // 这里可以实现异步搜索，现在简单处理
    const filtered = filteredStrategies.filter(option => 
      option.label.toLowerCase().includes(value.toLowerCase())
    );
    setFilteredStrategies(filtered);
  }

  const onCompare = async ()=>{
    if (selected.length < 2) return message.warning('请选择至少2个回测进行对比')
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

  // 过滤回测列表
  const filteredRuns = useMemo(() => {
    let filtered = [...runs];
    
    if (searchText) {
      filtered = filtered.filter(run => 
        run.code.toLowerCase().includes(searchText.toLowerCase())
      );
    }
    
    if (strategySearchText) {
      filtered = filtered.filter(run => 
        run.strategy.toLowerCase().includes(strategySearchText.toLowerCase())
      );
    }
    
    return filtered;
  }, [runs, searchText, strategySearchText]);

  const columns = [
    { title:'Strategy', dataIndex:'strategy', key:'strategy' },
    { title:'标的', dataIndex:'code', key:'code' },
    { title:'FromTime', dataIndex:'start_time', key:'start_time', render: formatDateTime },
    { title:'ToTime', dataIndex:'end_time', key:'end_time', render: formatDateTime },
    { title:'InitialCapital', dataIndex:'initial_capital', key:'initial_capital' },
    { title:'FinalCapital', dataIndex:'final_capital', key:'final_capital' },
    { title:'RunFinish', dataIndex:'created_at', key:'created_at', render: formatDateTime },
    {
      title:'详情',
      key:'detail',
      render: (_: any, record: { run_id: string }) => (
        <Button 
          type="link" 
          onClick={() => loadRunDetail(record.run_id)}
        >
          查看详情
        </Button>
      )
    }
  ]

  useEffect(() => {
    loadRuns()
  }, [])

  return (
    <>
      <Card title='Reports'>
        <Space style={{marginBottom:12}}>
          <Select
            placeholder="请选择或输入标的"
            style={{ width: 220, marginRight: 16 }}
            showSearch
            filterOption={false}
            allowClear
            onSearch={handleSymbolSearch}
            options={filteredSymbols}
            value={searchText}
            onChange={(value) => setSearchText(value)}
          />
          <Select
            placeholder="请选择或输入策略"
            style={{ width: 220, marginRight: 16 }}
            showSearch
            filterOption={false}
            allowClear
            onSearch={handleStrategySearch}
            options={filteredStrategies}
            value={strategySearchText}
            onChange={(value) => setStrategySearchText(value)}
          />
          <Button onClick={onCompare}>比较所选</Button>
          <Button onClick={loadRuns}>刷新</Button>
        </Space>
        <Table rowKey="run_id" dataSource={filteredRuns} columns={columns} rowSelection={{ 
          selectedRowKeys: selected, 
          onChange: (keys)=> setSelected(keys as string[])
        }} pagination={{pageSize:20}} />

        {compareData.length>0 && (
          <Card title="比较结果" style={{marginTop:16}}>
            <Table dataSource={compareData} rowKey="id" columns={[
              {title:'Sharpe', dataIndex:['metrics','sharpe'], key:'sharpe', render:(_,r)=> r.metrics.sharpe},
              {title:'Total Return', dataIndex:['metrics','total_return'], key:'total_return', render:(_,r)=> r.metrics.total_return},
              {title:'Max Drawdown', dataIndex:['metrics','max_drawdown'], key:'max_drawdown', render:(_,r)=> r.metrics.max_drawdown}
            ]} pagination={false} />
          </Card>
        )}
      </Card>

      {/* 详情弹窗 */}
      <Modal
        title="回测详情"
        open={detailModalVisible}
        onCancel={handleCloseDetailModal}
        footer={null}
        width={1200}
        style={{ maxHeight: '90vh', minWidth: '1000px' }}
        styles={{ body: { overflowY: 'auto', padding: '16px' } }}
      >
        {currentRunDetail && (
          <Tabs>
            {/* 基本信息 */}
            <Tabs.TabPane tab="基本信息" key="1">
              <div style={{padding: 16}}>
                <Space direction="vertical" style={{width: '100%'}}>
                  <div>
                    <strong>策略名称:</strong> {currentRunDetail.strategy}
                  </div>
                  <div>
                    <strong>标的代码:</strong> {currentRunDetail.code}
                  </div>
                  <div>
                    <strong>回测时间范围:</strong> {formatDateTime(currentRunDetail.start_time)} 至 {formatDateTime(currentRunDetail.end_time)}
                  </div>
                  <div>
                    <strong>初始资金:</strong> {currentRunDetail.initial_capital}
                  </div>
                  <div>
                    <strong>最终资金:</strong> {currentRunDetail.final_capital}
                  </div>
                  <div>
                    <strong>运行ID:</strong> {currentRunDetail.run_id}
                  </div>
                  <div>
                    <strong>创建时间:</strong> {formatDateTime(currentRunDetail.created_at)}
                  </div>
                </Space>
              </div>
            </Tabs.TabPane>

            {/* 结果指标 */}
            <Tabs.TabPane tab="结果指标" key="2">
              <div style={{padding: 16}}>
                <Space direction="vertical" style={{width: '100%'}}>
                  <Space style={{width: '100%', justifyContent: 'space-between'}}>
                    <Statistic title="初始资金" value={currentRunDetail.initial_capital} />
                    <Statistic title="最终资金" value={currentRunDetail.final_capital} />
                    <Statistic title="总收益率" value={((currentRunDetail.final_capital - currentRunDetail.initial_capital) / currentRunDetail.initial_capital * 100).toFixed(2)} suffix="%" />
                  </Space>
                  {currentRunEquity.length > 0 && (
                    <Space style={{width: '100%', justifyContent: 'space-between'}}>
                      <Statistic 
                        title="最大回撤" 
                        value={(currentRunEquity.reduce((max, item) => Math.min(max, item.drawdown), 0) * 100).toFixed(2)} 
                        suffix="%" 
                        valueStyle={{ color: '#f5222d' }}
                      />
                      <Statistic 
                        title="夏普率" 
                        value={(() => {
                          // 简单计算夏普率（假设无风险利率为0）
                          const returns = currentRunEquity.map((item: any, index: number) => {
                            if (index === 0) return 0
                            return (item.nav - currentRunEquity[index - 1].nav) / currentRunEquity[index - 1].nav
                          }).filter((r: number) => r !== 0)
                          
                          if (returns.length === 0) return 0
                          
                          const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length
                          const stdDev = Math.sqrt(returns.reduce((a, b) => a + Math.pow(b - meanReturn, 2), 0) / returns.length)
                          
                          return stdDev === 0 ? 0 : (meanReturn / stdDev * Math.sqrt(252)).toFixed(2) // 假设252个交易日
                        })()}
                      />
                    </Space>
                  )}
                </Space>
              </div>
            </Tabs.TabPane>

            {/* 收益曲线 */}
            <Tabs.TabPane tab="收益曲线" key="3">
              <div style={{padding: 16, height: 400}}>
                {prepareEquityChartData ? (
                  <ReactECharts option={prepareEquityChartData} style={{height: '100%'}} />
                ) : (
                  <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%'}}>
                    暂无收益曲线数据
                  </div>
                )}
              </div>
            </Tabs.TabPane>

            {/* 交易图表 */}
            <Tabs.TabPane tab="K线交易图" key="5">
              <div style={{padding: 16, height: 500}}>
                {prepareKlineWithTradesData ? (
                  <ReactECharts option={prepareKlineWithTradesData} style={{height: '100%'}} />
                ) : (
                  <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%'}}>
                    正在加载K线数据...
                  </div>
                )}
              </div>
            </Tabs.TabPane>

            {/* 模拟交易记录 */}
            <Tabs.TabPane tab="交易记录" key="4">
              <div style={{ padding: '8px 0', maxHeight: '600px', overflow: 'auto' }}>
                <div style={{ marginBottom: 16, textAlign: 'right' }}>
                  <Button 
                    onClick={() => {
                      if (currentRunTrades.length === 0) {
                        message.warning('没有可导出的交易记录');
                        return;
                      }
                       
                      // 准备导出数据
                      const exportData = currentRunTrades.map(trade => ({
                        '时间': formatDateTime(trade.datetime),
                        '标的': trade.code,
                        '方向': trade.side,
                        '价格': trade.price.toFixed(Math.min(4, trade.price.toString().split('.')[1]?.length || 0)),
                        '数量': trade.qty.toFixed(Math.min(4, trade.qty.toString().split('.')[1]?.length || 0)),
                        '金额': trade.amount.toFixed(Math.min(4, trade.amount.toString().split('.')[1]?.length || 0)),
                        '费用': trade.fee.toFixed(Math.min(4, trade.fee.toString().split('.')[1]?.length || 0)),
                        '盈亏': trade.realized_pnl ? trade.realized_pnl.toFixed(Math.min(4, trade.realized_pnl.toString().split('.')[1]?.length || 0)) : '-',
                        '净值': trade.nav ? trade.nav.toFixed(Math.min(4, trade.nav.toString().split('.')[1]?.length || 0)) : '-'
                      }));
                       
                      // 创建工作表
                      const ws = XLSX.utils.json_to_sheet(exportData);
                      
                      // 创建工作簿
                      const wb = XLSX.utils.book_new();
                      XLSX.utils.book_append_sheet(wb, ws, '交易记录');
                      
                      // 生成文件名，使用回测ID和当前日期
                      const filename = `交易记录_${currentRunDetail.id || 'unknown'}_${dayjs().format('YYYYMMDD_HHmmss')}.xlsx`;
                      
                      // 导出文件
                      XLSX.writeFile(wb, filename);
                      message.success('交易记录导出成功');
                    }}
                  >
                    导出Excel
                  </Button>
                </div>
                <Table 
                  dataSource={currentRunTrades}
                  rowKey={(record: any) => `${record.datetime}-${record.side}`}
                  pagination={{pageSize: 10}}
                  scroll={{ x: '1200px' }}
                  columns={[
                    {title: '时间', dataIndex: 'datetime', key: 'datetime', render: formatDateTime, width: 160},
                    {title: '标的', dataIndex: 'code', key: 'code', width: 100},
                    {title: '方向', dataIndex: 'side', key: 'side', width: 80},
                    {title: '价格', dataIndex: 'price', key: 'price', render: (value: number) => value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)), width: 100},
                    {title: '数量', dataIndex: 'qty', key: 'qty', render: (value: number) => value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)), width: 100},
                    {title: '金额', dataIndex: 'amount', key: 'amount', render: (value: number) => value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)), width: 100},
                    {title: '费用', dataIndex: 'fee', key: 'fee', render: (value: number) => value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)), width: 100},
                    {title: '盈亏', dataIndex: 'realized_pnl', key: 'realized_pnl', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 100},
                    {title: '净值', dataIndex: 'nav', key: 'nav', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 100}
                  ]}
                />
              </div>
            </Tabs.TabPane>
          </Tabs>
        )}
      </Modal>
    </>
  )
}

export default Reports
