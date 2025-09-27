import { ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { Card, Table, Button, Space, message, Select } from 'antd'
import { useState, useEffect, useMemo } from 'react'
import client from '../api/client'

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
  // 添加一些默认的mock数据，确保即使API调用失败，选择器也能显示placeholder
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredStrategies, setFilteredStrategies] = useState<{ value: string; label: string }[]>([])
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(20)
  const [sortField, setSortField] = useState<string>('totalReturn')
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend')
  const [loading, setLoading] = useState<boolean>(false)
  // TODO: 以下搜索相关状态暂时未使用，如有需要可以取消注释
  /*
  const [symbols, setSymbols] = useState<{ value: string; label: string }[]>([])
  const [strategies, setStrategies] = useState<{ value: string; label: string }[]>([])
  */
  const [fallbackRuns, setFallbackRuns] = useState<any[]>([])
  const [fallbackDataLoaded, setFallbackDataLoaded] = useState<boolean>(false)
  const [initialized, setInitialized] = useState<boolean>(false)

  // 共享的加载备选数据函数
  const loadFallbackData = async () => {
    try {
      if (fallbackDataLoaded) return fallbackRuns;
      
      const allRunsRes = await client.get('/api/runs', { params: { pageSize: 1000 } });
      setFallbackRuns(allRunsRes.data.rows || []);
      setFallbackDataLoaded(true);
      return allRunsRes.data.rows || [];
    } catch (error) {
      console.error('加载备选数据失败:', error);
      return [];
    }
  }

  // 从API加载标的数据
  const loadSymbols = async () => {
    try {
      const response = await client.get('/api/market/market_codes');
      const marketCodes = response.data.rows || [];
      
      // 格式化数据为Select组件需要的格式，使用excode字段
      const symbolData = marketCodes.map((item: any) => ({
        value: item.excode, // 提交时使用的字段
        label: `${item.excode}` // 显示的标签
      }));
      
      setFilteredSymbols(symbolData);
    } catch (error) {
      console.error('加载标的数据失败:', error);
      // 如果API调用失败，从回测记录中提取标的作为备选
      try {
        const fallbackData = await loadFallbackData();
        if (fallbackData.length > 0) {
          const symbols: string[] = Array.from(new Set(fallbackData.map((run: any) => run.code)));
          setFilteredSymbols(symbols.map((s) => ({ value: s, label: s })));
        } else {
          // 添加mock数据确保placeholder显示
          setFilteredSymbols([{value: 'mock', label: 'mock symbol'}]);
        }
      } catch (fallbackError) {
        console.error('加载备选标的数据也失败:', fallbackError);
        // 添加mock数据确保placeholder显示
        setFilteredSymbols([{value: 'mock', label: 'mock symbol'}]);
      }
    }
  }


  // 加载策略列表
  const loadStrategies = async () => {
    try {
      const response = await client.get('/api/strategies');
      const strategyList = response.data.rows || [];
      
      const strategyData = strategyList.map((strategy: any) => ({
        value: strategy.name,
        label: `${strategy.name}${strategy.description ? ` - ${strategy.description}` : ''}`
      }));
      
      setFilteredStrategies(strategyData);
    } catch (error) {
      console.error('加载策略列表失败:', error);
      // 如果API调用失败，从回测记录中提取策略作为备选
      try {
        const fallbackData = await loadFallbackData();
        if (fallbackData.length > 0) {
          const strategies: string[] = Array.from(new Set(fallbackData.map((run: any) => run.strategy)));
          setFilteredStrategies(strategies.map((s) => ({ value: s, label: s })));
        } else {
          // 添加mock数据确保placeholder显示
          setFilteredStrategies([{value: 'mock', label: 'mock strategy'}]);
        }
      } catch (fallbackError) {
        console.error('加载备选策略数据也失败:', fallbackError);
        // 添加mock数据确保placeholder显示
        setFilteredStrategies([{value: 'mock', label: 'mock strategy'}]);
      }
    }
  }

  // 查看详情处理函数
  const handleViewDetail = (runId: string) => {
    navigate(`/reports/${runId}`)
  }


  // 单条删除处理函数
  const handleSingleDelete = async (runId: string) => {
    try {
      await client.delete(`/api/runs/${runId}`);
      message.success('删除成功');
      // 重新加载数据
      loadRuns(currentPage, pageSize);
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请重试');
    }
  }

  // 批量删除处理函数
  const handleBatchDelete = async () => {
    if (selected.length === 0) {
      message.warning('请选择要删除的回测报告');
      return;
    }

    try {
      // 修改为与后端API匹配的POST请求
      await client.post('/api/runs/batch_delete', {
        ids: selected
      });
      message.success(`成功删除 ${selected.length} 条回测报告`);
      // 清空选择
      setSelected([]);
      // 重新加载数据
      loadRuns(currentPage, pageSize);
    } catch (error) {
      console.error('批量删除失败:', error);
      message.error('批量删除失败，请重试');
    }
  }

  // 加载回测列表
  const loadRuns = async (page: number = currentPage, size: number = pageSize) => {
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
    } catch (error) {
      console.error('加载回测列表失败:', error)
      message.error('加载回测列表失败')
    } finally {
      // 无论成功或失败，最后都设置loading为false
      setLoading(false)
    }
  }

  // TODO: 以下搜索函数暂时未使用，如有需要可以取消注释
  /*
  // 使用useCallback缓存搜索函数
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
  */

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
      setSortField(sorter.field);
      setSortOrder(sorter.order);
      
      // 重置到第一页，因为排序后的数据分布可能完全不同
      setCurrentPage(1);
      // 重新加载数据
      loadRuns(1, pageSize);
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
      title: '操作',
      key: 'action',
      render: (_: any, record: { run_id: string }) => (
        <>
          <Button 
            type="link" 
            onClick={() => handleViewDetail(record.run_id)}
          >
            查看详情
          </Button>
          <Button 
            type="link" 
            danger 
            onClick={() => {
              if (window.confirm('确定要删除这条回测报告吗？')) {
                handleSingleDelete(record.run_id);
              }
            }}
          >
            删除
          </Button>
        </>
      )
    }
  ]

  // 初始加载数据
  useEffect(() => {
    if (initialized) return;

    const initializeData = async () => {
      try {
        // 并行加载所有初始数据，但只调用一次
        await Promise.all([
          loadSymbols(),
          loadStrategies()
        ]);
        // 等待其他数据加载完成后再加载回测列表
        await loadRuns();
        // 设置初始化完成标志
        setInitialized(true);
      } catch (error) {
        console.error('初始化数据加载失败:', error);
      }
    };

    initializeData();
  }, [initialized])

  // 监听排序状态和分页变化，触发数据重新加载
  useEffect(() => {
    // 防止在组件初始化时重复调用loadRuns
    // 只有在初始化完成后且状态发生实际变化时才重新加载数据
    if (!initialized) return;
    
    loadRuns(currentPage, pageSize);
  }, [sortField, sortOrder, currentPage, pageSize, initialized])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Card title='回测报告' className="shadow-lg" style={{ borderRadius: '12px', overflow: 'hidden', flex: 1 }}>
        <Space style={{marginBottom:16, display: 'flex', flexWrap: 'wrap', gap: 16}}>
           <Select
            placeholder="请选择或输入策略"
            style={{ width: 320 }}
            showSearch
            allowClear
            options={filteredStrategies}
            value={strategySearchText || undefined}
            onChange={(value) => {
              setStrategySearchText(value)
              handleSearchChange()
            }}
          />
          <Select
            placeholder="请选择或输入标的"
            style={{ width: 320 }}
            showSearch
            allowClear
            options={filteredSymbols}
            value={searchText || undefined}
            onChange={(value) => {
              setSearchText(value)
              handleSearchChange()
            }}
          />
          <Button 
            icon={<ReloadOutlined />}
            onClick={() => loadRuns(currentPage, pageSize)}
            className="transition-all duration-300 hover:shadow-md"
          >
            刷新
          </Button>
          <Button 
            type="primary" 
            danger
            onClick={handleBatchDelete}
            disabled={selected.length === 0}
            className="transition-all duration-300 hover:shadow-md"
          >
            批量删除
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
          scroll={{ x: 1200, y: 600 }}
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条记录`,
            pageSizeOptions: ['10', '20', '50', '100'],
            showLessItems: false,
            size: 'default',
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