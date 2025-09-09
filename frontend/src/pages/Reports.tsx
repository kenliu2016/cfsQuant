
import { Card, Table, Button, Space, message, Select, Modal, Tabs, Statistic } from 'antd'
import { useEffect, useState, useMemo, useCallback } from 'react'
import client from '../api/client'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'

// 格式化日期时间函数
const formatDateTime = (dateString: string) => {
  if (!dateString) return ''
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

export default function Reports(){
  const [runs, setRuns] = useState<any[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [compareData, setCompareData] = useState<any[]>([])
  const [sortMetric, _setSortMetric] = useState<string>('sharpe')
  const [symbols, setSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])
  const [searchText, setSearchText] = useState<string | undefined>(undefined)
  const [strategies, setStrategies] = useState<{ value: string; label: string }[]>([])
  const [filteredStrategies, setFilteredStrategies] = useState<{ value: string; label: string }[]>([])
  const [strategySearchText, setStrategySearchText] = useState<string | undefined>(undefined)
  
  // 详情弹窗状态
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [currentRunDetail, setCurrentRunDetail] = useState<any>(null)
  const [currentRunEquity, setCurrentRunEquity] = useState<any[]>([])
  const [currentRunTrades, setCurrentRunTrades] = useState<any[]>([])

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

  // 从后端加载策略数据
  const loadStrategies = async () => {
    try {
      const response = await client.get('/strategies');
      const strategyList = response.data.rows || [];
      
      // 格式化策略数据为Select组件需要的格式
      const formattedStrategies = strategyList.map((s: any) => ({
        value: s.name,
        label: s.name
      }));
      
      setStrategies(formattedStrategies);
      setFilteredStrategies(formattedStrategies);
    } catch (error) {
      console.error('加载策略数据失败:', error);
    }
  }

  useEffect(() => {
    loadSymbols();
    loadStrategies();
    loadRuns();
  }, [])

  const loadRuns = async ()=>{
    const res = await client.get('/runs?limit=200')
    setRuns(res.data.rows || [])
  }

  // 加载回测详情
  const loadRunDetail = async (runId: string) => {
    try {
      console.log('加载回测详情，runId:', runId)
      
      // 先显示弹窗，防止因为API调用失败而不显示
      setDetailModalVisible(true)
      
      // 只调用一个API端点获取所有回测详情数据
      try {
        const runResponse = await client.get(`/runs/${runId}`)
        const detailData = runResponse.data
        
        // 提取并设置回测基本信息
        setCurrentRunDetail(detailData.info || {})
        
        // 提取并设置回测equity数据
        setCurrentRunEquity(detailData.equity || [])
        
        // 提取并设置交易记录数据
        setCurrentRunTrades(detailData.trades || [])
        
        console.log('成功加载回测详情数据')
      } catch (error) {
        console.error('加载回测详情数据失败:', error)
        message.error('加载回测详情失败')
        
        // 设置默认空数据，避免显示错误
        setCurrentRunDetail({})
        setCurrentRunEquity([])
        setCurrentRunTrades([])
      }
    } catch (error) {
      console.error('加载回测详情失败:', error)
      message.error('加载回测详情失败')
      // 确保弹窗显示
      setDetailModalVisible(true)
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

  // 使用useCallback缓存标的搜索函数
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

  // 使用useCallback缓存策略搜索函数
  const handleStrategySearch = useCallback((inputValue: string) => {
    if (!inputValue) {
      setFilteredStrategies(strategies);
      return;
    }
    
    const lowerInput = inputValue.toLowerCase();
    const filtered = strategies.filter(strategy => 
      strategy.value.toLowerCase().includes(lowerInput) ||
      strategy.label.toLowerCase().includes(lowerInput)
    );
    setFilteredStrategies(filtered);
  }, [strategies])

  // 使用useMemo缓存过滤后的运行数据
  const filteredRuns = useMemo(() => {
    let filtered = runs;
    
    // 根据标的搜索过滤
    if (searchText) {
      const lowerSearch = searchText.toLowerCase();
      filtered = filtered.filter(run => 
        run.code.toLowerCase().includes(lowerSearch)
      );
    }
    
    // 根据策略搜索过滤
    if (strategySearchText) {
      const lowerStrategySearch = strategySearchText.toLowerCase();
      filtered = filtered.filter(run => 
        run.strategy.toLowerCase().includes(lowerStrategySearch)
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
        width={1000}
      >
        {currentRunDetail && (
          <Tabs defaultActiveKey="1">
            {/* 回测参数 */}
            <Tabs.TabPane tab="回测参数" key="1">
              <div style={{padding: 16}}>
                <div style={{marginBottom: 12}}>
                  <strong>策略:</strong> {currentRunDetail.strategy}
                </div>
                <div style={{marginBottom: 12}}>
                  <strong>标的:</strong> {currentRunDetail.code}
                </div>
                <div style={{marginBottom: 12}}>
                  <strong>数据区间:</strong> {formatDateTime(currentRunDetail.start_time)} - {formatDateTime(currentRunDetail.end_time)}
                </div>
                <div>
                  <strong>执行参数:</strong>
                  {currentRunDetail.paras && typeof currentRunDetail.paras === 'object' && Object.keys(currentRunDetail.paras).length > 0 ? (
                    <ul>
                      {Object.entries(currentRunDetail.paras as Record<string, any>).map(([key, value]) => (
                        <li key={key}>
                          {key}: {typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>暂无执行参数</p>
                  )}
                </div>
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
                        title="年化收益率" 
                        value={(() => {
                          // 计算年化收益率（简单计算）
                          const days = (new Date(currentRunDetail.end_time).getTime() - new Date(currentRunDetail.start_time).getTime()) / (1000 * 60 * 60 * 24)
                          const annualizedReturn = ((currentRunDetail.final_capital / currentRunDetail.initial_capital) ** (365 / days) - 1) * 100
                          return annualizedReturn.toFixed(2)
                        })()}
                        suffix="%" 
                      />
                      <Statistic 
                        title="最大回撤" 
                        value={Math.min(...currentRunEquity.map((item: any) => item.drawdown)).toFixed(2)}
                        suffix="%" 
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

            {/* 模拟交易记录 */}
            <Tabs.TabPane tab="交易记录" key="4">
              <Table 
                dataSource={currentRunTrades}
                rowKey={(record: any) => `${record.datetime}-${record.side}`}
                pagination={{pageSize: 10}}
                columns={[
                  {title: '时间', dataIndex: 'datetime', key: 'datetime', render: formatDateTime},
                  {title: '标的', dataIndex: 'code', key: 'code'},
                  {title: '方向', dataIndex: 'side', key: 'side'},
                  {title: '价格', dataIndex: 'price', key: 'price'},
                  {title: '数量', dataIndex: 'qty', key: 'qty'},
                  {title: '金额', dataIndex: 'amount', key: 'amount'},
                  {title: '费用', dataIndex: 'fee', key: 'fee'}
                ]}
              />
            </Tabs.TabPane>
          </Tabs>
        )}
      </Modal>
    </>
  )
}
