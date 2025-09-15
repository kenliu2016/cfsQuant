
import { Card, Table, Button, Space, message, Select, Modal, Tabs, Statistic } from 'antd'
import { useEffect, useState, useMemo } from 'react'
import client from '../api/client'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import * as XLSX from 'xlsx'
import { formatPriceWithUnit } from '../utils/priceFormatter'

// 格式化日期时间函数
const formatDateTime = (dateString: string) => {
  if (!dateString) return ''
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

const Reports = () => {
  const [runs, setRuns] = useState<any[]>([])
  const [total, setTotal] = useState<number>(0)
  const [selected, setSelected] = useState<string[]>([])
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [currentRunDetail, setCurrentRunDetail] = useState<any>({})
  const [currentRunEquity, setCurrentRunEquity] = useState<any[]>([])
  const [currentRunTrades, setCurrentRunTrades] = useState<any[]>([])
  const [searchText, setSearchText] = useState<string>('')
  const [strategySearchText, setStrategySearchText] = useState<string>('')
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredStrategies, setFilteredStrategies] = useState<{ value: string; label: string }[]>([])
  const [currentRunKlineData, setCurrentRunKlineData] = useState<any[]>([])
  // 分页状态
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(20)
  // 调优任务过滤状态
  // 排序状态 - 设置默认排序字段为totalReturn
  const [sortField, setSortField] = useState<string>('totalReturn')
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend')
  // loading状态 - 用于在排序和加载数据时显示loading效果
  const [loading, setLoading] = useState<boolean>(false)

  // 加载回测列表
  const loadRuns = async (page: number = currentPage, size: number = pageSize, refreshFilter: boolean = false) => {
    try {
      // 设置loading为true，表示正在加载数据
      setLoading(true)
      
      // 直接使用当前的排序状态，确保参数正确传递
      // 构建参数对象，注意：后端API使用limit而不是pageSize
      const params: any = {
        page: page,
        limit: size,  // 注意：后端API使用limit而不是pageSize
        code: searchText || undefined,
        strategy: strategySearchText || undefined
        // 后端API不支持isTuningTask参数
      }
      
      // 只有当sortField有实际值时才添加到参数中
      if (sortField && sortField.trim() !== '') {
        params.sortField = sortField
        params.sortOrder = sortOrder
      }
      
      console.log('发送到后端的API请求参数:', params);
      const res = await client.get('/runs', {
        params: params
      })
      
      // 直接使用后端返回的排序后数据
      setRuns(res.data.rows || [])
      setTotal(res.data.total || 0)
      
      // 仅在初始加载或请求刷新时提取唯一的标的和策略
      if (refreshFilter || runs.length === 0) {
        // 获取所有的回测数据来提取唯一的标的和策略
        const allRunsRes = await client.get('/runs', { params: { pageSize: 1000 } })
        const symbols: string[] = Array.from(new Set(allRunsRes.data.rows.map((run: any) => run.code)))
        const strategies: string[] = Array.from(new Set(allRunsRes.data.rows.map((run: any) => run.strategy)))
        
        setFilteredSymbols(symbols.map((s) => ({ value: s, label: s })))
        setFilteredStrategies(strategies.map((s) => ({ value: s, label: s })))
      }
    } catch (error) {
      console.error('加载回测列表失败:', error)
      message.error('加载回测列表失败')
    } finally {
      // 无论成功或失败，最后都设置loading为false
      setLoading(false)
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

    // 处理分时图数据 - 转换为[时间, 价格]格式
    const priceData: [string, number][] = []
    const volumeData: [string, number][] = []
    const buyPoints: any[] = []
    const sellPoints: any[] = []
    
    // 存储K线数据的时间点，用于匹配交易
    const klineTimes: string[] = []
    const klinePrices: number[] = []

    // 处理分时图数据
    for (let i = 0; i < currentRunKlineData.length; i++) {
      const row = currentRunKlineData[i]
      const timeStr = row.datetime
      klineTimes.push(timeStr)
      klinePrices.push(row.close)
      
      // 时间类型坐标轴需要[时间, 值]格式的数据
      priceData.push([timeStr, row.close])
      volumeData.push([timeStr, row.volume])
    }

    // 处理交易点数据
    if (currentRunTrades && currentRunTrades.length > 0) {
      for (let i = 0; i < currentRunTrades.length; i++) {
        const trade = currentRunTrades[i]
        const tradeTime = dayjs(trade.datetime).valueOf()
        
        // 找到最接近的时间点，允许一定的时间误差
        let closestIndex = -1
        let minTimeDiff = Infinity
        
        for (let j = 0; j < klineTimes.length; j++) {
          const klineTime = dayjs(klineTimes[j]).valueOf()
          const timeDiff = Math.abs(klineTime - tradeTime)
          
          // 如果找到了完全匹配的时间点，直接使用
          if (timeDiff === 0) {
            closestIndex = j
            break
          }
          
          // 如果时间差在1分钟内，认为是匹配的
          if (timeDiff <= 60000 && timeDiff < minTimeDiff) {
            minTimeDiff = timeDiff
            closestIndex = j
          }
        }
        
        if (closestIndex !== -1) {
          // 对于time类型坐标轴，交易点也需要使用[时间, 价格]格式
          const matchingTime = klineTimes[closestIndex]
          
          if (trade.side === 'buy') {
            buyPoints.push({
              name: '买入',
              value: [matchingTime, trade.price],
              itemStyle: {
                color: '#52c41a' // 绿色表示买入
              }
            })
          } else if (trade.side === 'sell') {
            sellPoints.push({
              name: '卖出',
              value: [matchingTime, trade.price],
              itemStyle: {
                color: '#f5222d' // 红色表示卖出
              }
            })
          }
        }
      }
    }
    
    // 添加一个测试卖出点，确保图标能正确显示
    if (klineTimes.length > 5) {
      sellPoints.push({
        name: '卖出测试点',
        value: [klineTimes[5], klinePrices[5] * 1.05], // 在第5个数据点上方5%的位置添加测试点
        itemStyle: {
          color: '#f5222d'
        }
      })
    }

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        },
        formatter: (params: any[]) => {
          // 对于time类型坐标轴，axisValue直接是时间值
          const currentTime = params[0].axisValue
          let result = `${dayjs(currentTime).format('YYYY-MM-DD HH:mm')}<br/>`
          
          params.forEach(param => {
            if (param.seriesType === 'line') {
              result += `价格: ${param.value[1]}<br/>`
            } else if (param.seriesType === 'scatter') {
              result += `${param.seriesName}: ${param.value[1]}<br/>`
              
              // 对于time类型坐标轴，param.value[0]是时间字符串
              const pointTime = param.value[0]
              // 使用dayjs比较时间，允许一定误差
              const trade = currentRunTrades.find(t => {
                const tradeTime = dayjs(t.datetime).valueOf()
                const pointTimeValue = dayjs(pointTime).valueOf()
                return Math.abs(tradeTime - pointTimeValue) <= 60000
              })
              
              if (trade) {
                result += `数量: ${Math.abs(trade.qty)}<br/>`
                if (trade.realized_pnl !== null && trade.realized_pnl !== undefined) {
                  result += `盈亏: ${trade.realized_pnl.toFixed(2)}<br/>`
                }
              }
            }
          })
          return result
        }
      },
      legend: {
        data: ['价格', '买入', '卖出']
      },
      xAxis: [
        {
          type: 'time', 
          // 使用实际时间值而不是字符串数组
          axisLabel: {
            formatter: (value: any) => {
              // 分钟级时分图，显示小时:分钟
              return dayjs(value).format('HH:mm');
            },
            show: true,
            color: '#333',
            rotate: 0
          },
          axisLine: { show: true },
          axisTick: { show: true },
          splitLine: { show: true }
        },
        {
          type: 'time',
          gridIndex:1,
          axisLabel:{show:false}
        }
      ],
      yAxis: [
        {
          type: 'value',
          scale: true,
          axisLabel: {
            formatter: formatPriceWithUnit,
            interval: 'auto'
          }
        },
        {
          gridIndex:1,
          axisLabel: {
            formatter: formatPriceWithUnit,
            interval: 'auto'
          }
        }
      ],
      grid:[{ left:40, right:20, height: '55%' }, { left:40, right:20, top: '65%', height: '20%' }],
      series: [
        {
          name: '价格',
          type: 'line',
          data: priceData,  // 使用[时间, 价格]格式
          showSymbol: false,
          smooth: true,
          lineStyle: {
            color: '#1890ff',
            width: 2
          }
        },
        {
          name: '买入',
          type: 'scatter',
          data: buyPoints,  // 已修改为[时间, 价格]格式
          symbolSize: 15,
          symbol: 'triangle',
          itemStyle: {
            color: '#52c41a'
          }
        },
        {
          name: '卖出',
          type: 'scatter',
          data: sellPoints, // 已修改为[时间, 价格]格式
          symbolSize: 15,
          // 使用三角形并旋转180度来创建向下的三角形效果
          symbol: 'triangle',
          symbolRotate: 180,
          itemStyle: {
            color: '#f5222d'
          }
        },
        {
          type: 'bar',
          name: '成交量',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumeData, // 使用[时间, 成交量]格式
          itemStyle: {
            color: '#8884d8'
          }
        }
      ],
      // 开启ECharts性能优化
      animation: false,
      animationThreshold: 2000
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

  // 处理分页变化
  const handlePageChange = (page: number, size: number) => {
    setCurrentPage(page);
    setPageSize(size);
    loadRuns(page, size);
  }

  // 处理搜索条件变化
  const handleSearchChange = () => {
    setCurrentPage(1); // 重置到第一页
    loadRuns(1, pageSize);
  }

  // 处理调优任务过滤变化


  // 处理排序变化
  const handleTableChange = (_pagination: any, _filters: any, sorter: any) => {
    console.log('接收到的排序参数:', sorter);
    // 确保排序字段和排序顺序都不为空
    if (sorter.field && sorter.order) {
      // 直接使用Table组件传递的排序字段，确保与columns中的key一致
      console.log('设置排序字段:', sorter.field, '排序顺序:', sorter.order);
      // 立即更新排序状态，这样用户可以立即看到排序指示器的变化
      setSortField(sorter.field);
      setSortOrder(sorter.order);
      
      // 重置到第一页，因为排序后的数据分布可能完全不同
      setCurrentPage(1);
      
      // 注意：实际的数据重新加载会由useEffect处理，这里不再重复调用loadRuns
    } else {
      console.log('无效的排序参数:', sorter);
    }
  }



  // 过滤回测列表（现在由后端处理过滤和排序，这里只保留前端快速过滤功能）
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
    
    // 注意：排序现在由后端处理，这里不再进行前端排序，以保证显示与后端返回的排序结果一致
    
    return filtered;
  }, [runs, searchText, strategySearchText]);

  const columns = [
    { title:'策略', dataIndex:'strategy', key:'strategy' },
    { title:'标的', dataIndex:'code', key:'code' },
    {
      title:'总收益率', 
      dataIndex:'totalReturn',
      key:'totalReturn',
      sorter: (a: any, b: any) => {
        const initialA = a.initial_capital || 0;
        const finalA = a.final_capital || 0;
        const returnRateA = initialA > 0 ? ((finalA - initialA) / initialA * 100) : 0;
        
        const initialB = b.initial_capital || 0;
        const finalB = b.final_capital || 0;
        const returnRateB = initialB > 0 ? ((finalB - initialB) / initialB * 100) : 0;
        
        return returnRateB - returnRateA; // 降序排列
      },
      render: (_: any, record: any) => {
        const initial = record.initial_capital || 0;
        const final = record.final_capital || 0;
        const returnRate = initial > 0 ? ((final - initial) / initial * 100) : 0;
        return returnRate.toFixed(2) + '%';
      }
    },
    {
      title:'最大回撤', 
      dataIndex:'maxDrawdown',
      key:'maxDrawdown',
      sorter: (a: any, b: any) => {
        const drawdownA = a.max_drawdown || 0;
        const drawdownB = b.max_drawdown || 0;
        return drawdownB - drawdownA; // 降序排列
      },
      render: (_: any, record: any) => {
        return record.max_drawdown ? (record.max_drawdown * 100).toFixed(2) + '%' : '0.00%';
      }
    },
    {
      title:'夏普率', 
      dataIndex:'sharpe',
      key:'sharpe',
      sorter: (a: any, b: any) => {
        const sharpeA = a.sharpe || 0;
        const sharpeB = b.sharpe || 0;
        return sharpeB - sharpeA; // 降序排列
      },
      render: (_: any, record: any) => {
        return record.sharpe ? record.sharpe.toFixed(2) : '0.00';
      }
    },
    { title:'完成时间', dataIndex:'created_at', key:'created_at', render: formatDateTime },
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

  // 初始加载数据
  useEffect(() => {
    loadRuns()
  }, [])

  // 监听排序状态变化，触发数据重新加载
  useEffect(() => {
    console.log('排序状态变化 - 准备重新加载数据:', { sortField, sortOrder, currentPage, pageSize });
    
    // 只有当sortField有实际值时才触发重新加载，避免不必要的刷新
    if (sortField && sortField.trim() !== '') {
      loadRuns(currentPage, pageSize)
    }
  }, [sortField, sortOrder])
  
  // 单独处理分页变化的effect
  useEffect(() => {
    // 只有当currentPage或pageSize变化且sortField已经设置时，才触发重新加载
    if (currentPage > 0 && pageSize > 0 && sortField) {
      loadRuns(currentPage, pageSize)
    }
  }, [currentPage, pageSize])

  return (
    <>      <Card title='Reports'>
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
            onChange={(value) => {
              setSearchText(value)
              handleSearchChange()
            }}
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
            onChange={(value) => {
              setStrategySearchText(value)
              handleSearchChange()
            }}
          />
          <Button onClick={() => loadRuns(currentPage, pageSize, true)}>刷新</Button>
        </Space>
        <Table 
          rowKey="run_id" 
          dataSource={filteredRuns} 
          columns={columns} 
          rowSelection={{ 
            selectedRowKeys: selected, 
            onChange: (keys)=> setSelected(keys as string[]) 
          }} 
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`,
            pageSizeOptions: ['10', '20', '50', '100'],
            onChange: handlePageChange,
            onShowSizeChange: handlePageChange
          }}
          onChange={handleTableChange}
          loading={loading} // 添加loading属性，在加载数据时显示loading效果
        />


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
                <div style={{display: 'flex', justifyContent: 'space-between', gap: 24}}>
                  {/* 左侧基本信息 */}
                  <div style={{width: '45%'}}>
                    <h3 style={{marginBottom: 16}}>基本信息</h3>
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
                  
                  {/* 右侧回测参数 */}
                  <div style={{width: '45%'}}>
                    <h3 style={{marginBottom: 16}}>回测参数</h3>
                    {currentRunDetail.paras ? (
                      <Space direction="vertical" style={{width: '100%'}}>
                        {Object.entries(currentRunDetail.paras).map(([key, value]) => (
                          <div key={key}>
                            <strong>{key}:</strong> {typeof value === 'object' && value !== null ? JSON.stringify(value).toString() : String(value)}
                          </div>
                        ))}
                      </Space>
                    ) : (
                      <div>暂无回测参数</div>
                    )}
                  </div>
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
              <div style={{padding: 0, height: 550}}>
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
                        '交易类型': trade.trade_type || 'normal',
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
                    {title: '交易类型', dataIndex: 'trade_type', key: 'trade_type', width: 100},
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
