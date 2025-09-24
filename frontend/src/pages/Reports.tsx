import { Card, Table, Button, Space, message, Select } from 'antd'
import { useEffect, useState, useMemo } from 'react'
import client from '../api/client'
import { ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'

// 格式化日期时间函数
const formatDateTime = (dateString: string) => {
  if (!dateString) return ''
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

const Reports = () => {
  const navigate = useNavigate()
  const [runs, setRuns] = useState<any[]>([])
  const [total, setTotal] = useState<number>(0)
  const [selected, setSelected] = useState<string[]>([])
  const [searchText, setSearchText] = useState<string>('')
  const [strategySearchText, setStrategySearchText] = useState<string>('')
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredStrategies, setFilteredStrategies] = useState<{ value: string; label: string }[]>([])
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(20)
  const [sortField, setSortField] = useState<string>('totalReturn')
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend')
  const [loading, setLoading] = useState<boolean>(false)

  // 查看详情处理函数
  const handleViewDetail = (runId: string) => {
    navigate(`/reports/${runId}`)
  }

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
      

      const res = await client.get('/api/runs', {
        params: params
      })
      
      // 直接使用后端返回的排序后数据
      setRuns(res.data.rows || [])
      setTotal(res.data.total || 0)
      
      // 仅在初始加载或请求刷新时提取唯一的标的和策略
      if (refreshFilter || runs.length === 0) {
        // 获取所有的回测数据来提取唯一的标的和策略
        const allRunsRes = await client.get('/api/runs', { params: { pageSize: 1000 } })
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

  // 处理排序变化
  const handleTableChange = (_pagination: any, _filters: any, sorter: any) => {
    // 确保排序字段和排序顺序都不为空
    if (sorter.field && sorter.order) {
      // 直接使用Table组件传递的排序字段，确保与columns中的key一致

      // 立即更新排序状态，这样用户可以立即看到排序指示器的变化
      setSortField(sorter.field);
      setSortOrder(sorter.order);
      
      // 重置到第一页，因为排序后的数据分布可能完全不同
      setCurrentPage(1);
      
      // 注意：实际的数据重新加载会由useEffect处理，这里不再重复调用loadRuns
    } else {
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
    {
      title:'交易次数',
      dataIndex:'trade_count',
      key:'trade_count',
      sorter: (a: any, b: any) => {
        const countA = a.trade_count || 0;
        const countB = b.trade_count || 0;
        return countB - countA; // 降序排列
      },
      render: (_: any, record: any) => {
        return record.trade_count || 0;
      }
    },
    {
      title:'胜率',
      dataIndex:'win_rate',
      key:'win_rate',
      sorter: (a: any, b: any) => {
        const rateA = a.win_rate || 0;
        const rateB = b.win_rate || 0;
        return rateB - rateA; // 降序排列
      },
      render: (_: any, record: any) => {
        return record.win_rate ? (record.win_rate * 100).toFixed(2) + '%' : '0.00%';
      }
    },
    {
      title:'收益率', 
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
      title:'总收益',
      dataIndex:'total_profit',
      key:'total_profit',
      sorter: (a: any, b: any) => {
        const profitA = a.total_profit || 0;
        const profitB = b.total_profit || 0;
        return profitB - profitA; // 降序排列
      },
      render: (_: any, record: any) => {
        return record.total_profit ? record.total_profit.toFixed(2) : '0.00';
      }
    },
    {
      title:'总手续费',
      dataIndex:'total_fee',
      key:'total_fee',
      sorter: (a: any, b: any) => {
        const feeA = a.total_fee || 0;
        const feeB = b.total_fee || 0;
        return feeB - feeA; // 降序排列
      },
      render: (_: any, record: any) => {
        return record.total_fee ? record.total_fee.toFixed(2) : '0.00';
      }
    },
    { title:'完成时间', dataIndex:'created_at', key:'created_at', render: formatDateTime },
    {
      title: '详情',
      key: 'detail',
      render: (_: any, record: { run_id: string }) => (
        <Button 
          type="link" 
          onClick={() => handleViewDetail(record.run_id)}
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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Card title='回测报告' className="shadow-lg" style={{ borderRadius: '12px', overflow: 'hidden', flex: 1 }}>
        <Space style={{marginBottom:16, display: 'flex', flexWrap: 'wrap', gap: 16}}>
          <Select
            placeholder="请选择或输入标的"
            style={{ width: 220 }}
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
            className="transition-all duration-300 hover:shadow-md"
          />
          <Select
            placeholder="请选择或输入策略"
            style={{ width: 220 }}
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
            className="transition-all duration-300 hover:shadow-md"
          />
          <Button 
            icon={<ReloadOutlined />}
            onClick={() => loadRuns(currentPage, pageSize, true)}
            className="transition-all duration-300 hover:shadow-md"
          >
            刷新
          </Button>
        </Space>
        <Table 
          rowKey="run_id" 
          dataSource={filteredRuns} 
          columns={columns} 
          rowSelection={{ 
            selectedRowKeys: selected, 
            onChange: (keys)=> setSelected(keys as string[]) 
          }} 
          className="shadow-sm rounded-lg overflow-hidden"
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条记录`,
            pageSizeOptions: ['10', '20', '50', '100'],
            onChange: handlePageChange,
            onShowSizeChange: handlePageChange
          }}
          onChange={handleTableChange}
          loading={loading}
        />
      </Card>
    </div>
  )
}

export default Reports