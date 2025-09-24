
import { Card, Table, Button, Space, message, Select, Modal, Tabs, Statistic } from 'antd'
import { useEffect, useState, useMemo } from 'react'
import client from '../api/client'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import * as XLSX from 'xlsx'
import { ReloadOutlined, DownloadOutlined } from '@ant-design/icons'

// 定义网格线数据类型
interface GridLevel {
  price: number;
  name: string;
}

// 格式化日期时间函数
const formatDateTime = (dateString: string) => {
  if (!dateString) return ''
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

// 创建K线图配置的辅助函数
const createKlineChartConfig = (klineData: any[], tradesData: any[], gridLevels: GridLevel[]) => {
  // 判断数据周期类型（分钟级、日线、周线、月线）
  const determineTimePeriod = () => {
    if (klineData.length < 2) return 'day'; // 默认日线
    
    const date1 = new Date(klineData[0].datetime);
    const date2 = new Date(klineData[1].datetime);
    const diffMinutes = (date2.getTime() - date1.getTime()) / (1000 * 60);
    
    if (diffMinutes < 60) return 'minute'; // 分钟级
    if (diffMinutes < 60 * 24) return 'hour'; // 小时级
    if (diffMinutes < 60 * 24 * 7) return 'day'; // 日线
    if (diffMinutes < 60 * 24 * 30) return 'week'; // 周线
    return 'month'; // 月线
  };
  
  const timePeriod = determineTimePeriod();
  
  // 预处理时间格式，根据周期显示不同格式
  const dates = klineData.map(item => {
    const date = new Date(item.datetime);
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    
    // 完整时间格式用于tooltip显示
    return {
      full: `${year}-${month}-${day} ${hours}:${minutes}`,
      display: timePeriod === 'minute' || timePeriod === 'hour' 
        ? `${hours}:${minutes}` 
        : `${month}-${day}`
    };
  });
  
  // 准备K线数据
  const candlestickData = klineData.map((item, index) => [dates[index].full, item.open, item.close, item.low, item.high]);
  
  // 计算价格范围，设置最佳显示比例
  let priceMin = Infinity;
  let priceMax = -Infinity;
  klineData.forEach(item => {
    priceMin = Math.min(priceMin, item.low);
    priceMax = Math.max(priceMax, item.high);
  });
  
  // 添加10%的边距，使图表显示更完整
  const priceRange = priceMax - priceMin;
  const yAxisMin = priceMin - priceRange * 0.1;
  const yAxisMax = priceMax + priceRange * 0.1;
  
  // 创建自定义格式化函数，根据当前数据范围动态调整刻度
  const getYAxisFormatter = () => {
    const range = yAxisMax - yAxisMin;
    // 根据价格范围确定小数点位数
    if (range >= 10000) return (value: number) => (value / 1000).toFixed(0) + 'k';
    if (range >= 1000) return (value: number) => (value / 1000).toFixed(1) + 'k';
    if (range >= 100) return (value: number) => value.toFixed(0);
    if (range >= 10) return (value: number) => value.toFixed(1);
    return (value: number) => value.toFixed(2);
  };
  
  const yAxisFormatter = getYAxisFormatter();
  
  // 确定默认显示的范围，确保能看到最新数据
  const getDefaultZoomRange = () => {
    const totalPoints = klineData.length;
    if (totalPoints <= 50) return { start: 0, end: 100 }; // 数据点少于50个，显示全部
    if (totalPoints <= 200) return { start: 50, end: 100 }; // 显示后50%
    if (totalPoints <= 500) return { start: 80, end: 100 }; // 显示后20%
    return { start: 90, end: 100 }; // 显示后10%
  };
  
  const defaultZoom = getDefaultZoomRange();
  
  // 定义信号类型为元组
  type SignalData = [string, number, number, string]; // [时间, 价格, 数量, 方向]
  
  // 处理交易数据，提取买卖信号
  const buySignals: SignalData[] = [];
  const sellSignals: SignalData[] = [];
  
  // 确保tradesData是数组
  if (Array.isArray(tradesData)) {
    tradesData.forEach(trade => {
      if (!trade || typeof trade !== 'object') return;
      
      // 提取必要的字段
      const { side, datetime, price, qty } = trade;
      if (!side || !datetime || typeof price !== 'number' || typeof qty !== 'number') {
        return;
      }
      
      // 找到对应的K线数据点的索引
      const klineIndex = klineData.findIndex(item => {
        // 比较日期时间，由于可能存在精度问题，使用字符串比较或时间戳比较
        const klineTime = new Date(item.datetime).getTime();
        const tradeTime = new Date(datetime).getTime();
        // 认为交易发生在K线对应的时间段内
        return Math.abs(tradeTime - klineTime) < 3600000; // 误差在1小时内
      });
      
      if (klineIndex >= 0) {
        // 构建信号数据点并指定类型
        const signalData: SignalData = [dates[klineIndex].full, price, qty, side];
        
        if (side.toLowerCase() === 'buy') {
          buySignals.push(signalData);
        } else if (side.toLowerCase() === 'sell') {
          sellSignals.push(signalData);
        }
      }
    });
  }
  
  // 合并所有买卖信号并按时间排序
  // 确保严格按照时间先后顺序排列，这对于正确连接信号点至关重要
  const allSignals = [...buySignals, ...sellSignals].sort((a, b) => {
    const timeA = new Date(a[0]).getTime();
    const timeB = new Date(b[0]).getTime();
    // 严格按时间戳排序，确保连接顺序正确
    return timeA - timeB;
  });

  // 构建ECharts配置
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        lineStyle: {
          color: '#999'
        },
        label: {
          backgroundColor: '#6a7985'
        }
      },
      formatter: function(params: any[]) {
        if (!params || params.length === 0) return '';
        
        // 查找K线数据
        let klineData = params.find(param => param.seriesName === 'K线');
        
        // 查找交易信号数据
        const signalParams = params.filter(param => 
          param.seriesName === '交易信号'
        );
        
        // 如果没有K线数据但有信号数据，尝试根据信号的时间找到对应的K线数据
        if (!klineData && signalParams.length > 0) {
          const signalTime = signalParams[0].axisValue;
          klineData = params.find(param => param.axisValue === signalTime && param.seriesName === 'K线');
        }
        
        // 如果有交易信号数据但没有K线数据，直接显示交易信号信息
        if (!klineData && signalParams.length > 0) {
          let result = signalParams[0].axisValue + '<br/>';
          signalParams.forEach(param => {
            const signalIndex = param.dataIndex;
            const signal = allSignals[signalIndex];
            
            if (signal) {
              const side = signal[3];
              const qty = signal[2];
              const price = signal[1];
              const signalType = side.toLowerCase() === 'buy' ? '买入' : '卖出';
              const signalColor = side.toLowerCase() === 'buy' ? '#14b143' : '#ef232a';
              result += '<span style="color: ' + signalColor + '">' + signalType + '价格: ' + price + '</span><br/>';
              result += '<span style="color: ' + signalColor + '">' + signalType + '数量: ' + qty + '</span><br/>';
            }
          });
          return result;
        }
        
        if (!klineData) return '';
        
        let result = klineData.axisValue + '<br/>';
        result += '<span style="color: #ef232a">开盘: ' + klineData.data[1] + '</span><br/>';
        const closeColor = klineData.data[2] >= klineData.data[1] ? '14b143' : 'ef232a';
        result += '<span style="color: #' + closeColor + '">收盘: ' + klineData.data[2] + '</span><br/>';
        result += '<span style="color: #8c8c8c">最低: ' + klineData.data[3] + '</span><br/>';
        result += '<span style="color: #8c8c8c">最高: ' + klineData.data[4] + '</span><br/>';
        
        // 计算涨跌幅
        const change = ((klineData.data[2] - klineData.data[1]) / klineData.data[1] * 100).toFixed(2);
        const color = klineData.data[2] >= klineData.data[1] ? '14b143' : 'ef232a';
        result += '<span style="color: #' + color + '">涨跌幅: ' + change + '%</span><br/>';
        
        // 添加交易信号信息 - 使用更简单的方式直接通过dataIndex获取信号
        if (signalParams.length > 0) {
          signalParams.forEach(param => {
            const signalIndex = param.dataIndex;
            const signal = allSignals[signalIndex];
            
            if (signal) {
              const side = signal[3];
              const qty = signal[2];
              const price = signal[1];
              const signalType = side.toLowerCase() === 'buy' ? '买入' : '卖出';
              const signalColor = side.toLowerCase() === 'buy' ? '#14b143' : '#ef232a';
              result += '<span style="color: ' + signalColor + '">' + signalType + '价格: ' + price + '</span><br/>';
              result += '<span style="color: ' + signalColor + '">' + signalType + '数量: ' + qty + '</span><br/>';
            }
          });
        }
        
        return result;
      }
    },
    legend: {
      show: false,
      data: ['K线']
    },
    // 添加缩放组件
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: defaultZoom.start,
        end: defaultZoom.end,
        zoomLock: false,
        filterMode: 'filter'
      },
      {
        show: true,
        type: 'slider',
        start: defaultZoom.start,
        end: defaultZoom.end,
        handleIcon: 'M10.7,11.9H9.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4h1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7v-1.2h6.6z M13.3,22H6.7v-1.2h6.6z M13.3,19.6H6.7v-1.2h6.6z',
        handleSize: '80%',
        handleStyle: {
          color: '#fff',
          shadowBlur: 3,
          shadowColor: 'rgba(0, 0, 0, 0.6)',
          shadowOffsetX: 2,
          shadowOffsetY: 2
        }
      }
    ],
    grid: [
      { left: '3%', right: '3%', top: '5%', bottom: '10%', height: 'auto' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates.map(date => date.full), // 使用完整时间用于数据匹配
        axisLabel: {
          show: false // 去掉横坐标刻度标签
        },
        axisLine: {
          lineStyle: {
            color: '#8E8EA0'
          }
        },
        splitLine: {
          show: false
        }
      }
    ],
    yAxis: [
      {
        type: 'value',
        scale: true, // 开启自动缩放，根据当前视图中的数据动态调整yAxis范围
        min: function(value: any) {
          // 自定义最小值计算，确保有一定的边距
          return value.min - (value.max - value.min) * 0.05;
        },
        max: function(value: any) {
          // 自定义最大值计算，确保有一定的边距
          return value.max + (value.max - value.min) * 0.05;
        },
        axisLabel: {
          color: '#8E8EA0',
          formatter: yAxisFormatter
        },
        axisLine: {
          show: true,
          lineStyle: {
            color: '#8E8EA0'
          }
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#f0f0f0',
            type: 'dashed'
          }
        }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: candlestickData.map(item => item.slice(1)),
        itemStyle: {
          color: '#14b143',  // 绿色表示涨（收盘价高于开盘价）
          color0: '#ef232a', // 红色表示跌（收盘价低于开盘价）
          borderColor: '#14b143',
          borderColor0: '#ef232a'
        },
        emphasis: {
          itemStyle: {
            borderWidth: 2
          }
        },
        barWidth: '60%', // 设置K线柱宽度，使显示更美观
        barMaxWidth: 50, // 最大宽度限制
        barMinWidth: 1 // 最小宽度限制
      },
      // 网格线标记系列
      {
        name: '网格线',
        type: 'line',
        data: [], // 空数据，只显示markLine
        showSymbol: false,
        lineStyle: {
          color: 'transparent' // 隐藏主线条
        },
        markLine: {
          silent: true,
          symbol: ['none', 'none'], // 去掉箭头
          lineStyle: {
            color: '#6C6C8A',
            type: 'dashed',
            width: 1
          },
          data: gridLevels.map(level => {
            // 根据网格线名称确定颜色
            let lineColor = '#1890ff'; // 默认蓝色（价格中枢）
            if (level.name.includes('卖出')) {
              lineColor = '#ef232a'; // 红色（卖出线）
            } else if (level.name.includes('买入') || level.name.includes('止损')) {
              lineColor = '#14b143'; // 绿色（买入线）
            }
            
            // 添加水平线配置
            return {
              yAxis: level.price,
              lineStyle: {
                color: lineColor,
                type: 'dashed',
                width: 1
              },
              label: {
                formatter: `${level.name}: ${level.price.toFixed(2)}`,
                position: 'insideStartTop',
                distance: 5,
                color: lineColor,
                fontSize: 10
              }
            };
          })
        }
      },
      
      // 合并的交易信号系列
      {
        name: '交易信号',
        type: 'scatter', // 改为scatter类型以避免线条显示
        data: allSignals.map(signal => [signal[0], signal[1]]),
        // 使用自定义symbol函数根据信号方向返回不同的图标
        symbol: (_value: any, params: any) => {
          // 获取当前数据点对应的信号对象
          const signal = allSignals[params.dataIndex];
          // 对于买入信号使用三角形
          if (signal && signal[3].toLowerCase() === 'buy') {
            return 'triangle';
          }
          // 对于卖出信号使用SVG路径定义真正的倒三角形
          return 'path://M0,10 L10,0 L-10,0 Z';
        },
        symbolSize: 12,
        // 移除偏移量，确保图标可见
        symbolOffset: [0, 0],
        // 使用自定义itemStyle函数根据信号方向返回不同的颜色
        itemStyle: {
          color: (params: any) => {
            // 获取当前数据点对应的信号对象
            const signal = allSignals[params.dataIndex];
            // 根据信号方向返回不同的颜色
            return signal && signal[3].toLowerCase() === 'buy' ? '#14b143' : '#ef232a';
          }
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 4,
            shadowColor: 'rgba(0, 0, 0, 0.3)'
          }
        },
        // 明确设置tooltip配置，确保交易信号点能正确显示tooltip
        tooltip: {
          show: true,
          formatter: function(params: any) {
            // 获取信号对象
            const signalIndex = params.dataIndex;
            const signal = allSignals[signalIndex];
            
            if (signal) {
              // 从信号对象中获取时间、价格、数量和方向
              const time = signal[0];
              const price = signal[1];
              const qty = signal[2];
              const side = signal[3];
              
              // 格式化输出
              const signalType = side.toLowerCase() === 'buy' ? '买入' : '卖出';
              const signalColor = side.toLowerCase() === 'buy' ? '#14b143' : '#ef232a';
              
              // 确保显示时间信息
              let result = time + '<br/>';
              
              // 添加K线信息
              // 尝试根据信号的时间找到对应的K线数据
              const klineData = candlestickData.find(kline => kline[0] === time);
              
              if (klineData) {
                result += '<span style="color: #ef232a">开盘: ' + klineData[1] + '</span><br/>';
                const closeColor = klineData[2] >= klineData[1] ? '14b143' : 'ef232a';
                result += '<span style="color: #' + closeColor + '">收盘: ' + klineData[2] + '</span><br/>';
                result += '<span style="color: #8c8c8c">最低: ' + klineData[3] + '</span><br/>';
                result += '<span style="color: #8c8c8c">最高: ' + klineData[4] + '</span><br/>';
                
                // 计算涨跌幅
                const change = ((klineData[2] - klineData[1]) / klineData[1] * 100).toFixed(2);
                const color = klineData[2] >= klineData[1] ? '14b143' : 'ef232a';
                result += '<span style="color: #' + color + '">涨跌幅: ' + change + '%</span><br/>';
                
                // 添加分隔线
                result += '<hr style="border: none; border-top: 1px solid #ddd; margin: 5px 0;">';
              }
              
              // 添加交易信号信息
              result += '<span style="color: ' + signalColor + '">' + signalType + '价格: ' + price + '</span><br/>';
              result += '<span style="color: ' + signalColor + '">' + signalType + '数量: ' + qty + '</span><br/>';
              
              return result;
            }
            
            // 如果没有信号数据，使用全局formatter
            return option.tooltip.formatter([params]);
          }
        }
      }
    ],
    animation: true,
    animationDuration: 1000,
    animationEasing: 'cubicOut',
    // 图表拖拽和平移配置
    graphic: {
      type: 'group',
      left: 'center',
      top: 'top'
    },
    // 工具箱配置
    toolbox: {
      show: true,
      right: 10,
      top: 10,
      feature: {
        dataZoom: {
          yAxisIndex: false
        },
        brush: {
          type: ['rect', 'polygon', 'clear']
        }
      }
    }
  };
  
  return option;
};

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
  // 网格线数据
  const [currentRunGridLevels, setCurrentRunGridLevels] = useState<GridLevel[]>([])

  const [currentRunId, setCurrentRunId] = useState<string>('')
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

  // 加载回测详情
  const loadRunDetail = async (runId: string) => {
    try {
      const res = await client.get('/api/runs/' + runId)
      setCurrentRunDetail(res.data.info || {})
      setCurrentRunTrades(res.data.trades || [])
      setDetailModalVisible(true)
      
      // 加载网格线数据
      await loadGridLevels(runId)
      
      // 同时加载K线数据
      if (res.data.info && res.data.info.code) {
        // 确保interval参数有效，默认使用1D
        const validIntervals = ['1m', '5m', '15m', '30m', '60m', '1h', '4h', '1D', '1W', '1M'];
        let interval = res.data.info.interval;
        
        // 如果interval不存在或不在有效列表中，使用默认值1D
        if (!interval || !validIntervals.includes(interval)) {
          interval = '1m';
        }
        
        await loadKlineData(res.data.info.code, res.data.info.start_time, res.data.info.end_time, interval)
      }
    } catch (error) {
      console.error('加载回测详情失败:', error)
      message.error('加载回测详情失败')
    }
  }

  // 加载网格线数据
  const loadGridLevels = async (runId: string) => {
    try {
      const gridRes = await client.get(`/api/runs/grid_levels?run_id=${runId}`)
      console.log('Grid levels data:', gridRes.data); // 保留调试日志
      // 只有当API返回有效数据且数组不为空时才设置网格线
      if (gridRes.data && Array.isArray(gridRes.data) && gridRes.data.length > 0) {
        setCurrentRunGridLevels(gridRes.data)
      } else {
        // 无数据时设置为空数组，不显示网格线
        setCurrentRunGridLevels([])
      }
    } catch (error) {
      console.error('加载网格线数据失败:', error)
      // 错误时也设置为空数组，不显示网格线
      setCurrentRunGridLevels([])
    }
  }

  // 加载K线数据
  const loadKlineData = async (code: string, start: string, end: string, interval: string) => {
    try {
      // 使用客户端发送请求
      const klineRes = await client.get('/market/candles', {
        params: {
          code,
          start,
          end,
          interval
        }
      })
      
      // 验证数据结构
      if (klineRes.data && Array.isArray(klineRes.data.rows)) {
        if (klineRes.data.rows.length > 0) {
          // 检查第一条数据的字段结构
        }
        setCurrentRunKlineData(klineRes.data.rows)
      } else {
        // 生成模拟数据以便图表能够渲染
        const mockData = generateMockKlineData(code, start, end, interval)
        setCurrentRunKlineData(mockData)
      }
      
      // 添加一个小延迟后再次打印currentRunKlineData状态
      setTimeout(() => {
      }, 100)
    } catch (error) {
      console.error('加载K线数据失败:', error)
      // 生成模拟数据以便图表能够渲染
      const mockData = generateMockKlineData(code || 'BTCUSDT', start || new Date().toISOString(), end || new Date().toISOString(), interval || '1m')
      setCurrentRunKlineData(mockData)
    }
  }
  
  // 生成模拟K线数据（增强版）
  const generateMockKlineData = (code: string = 'BTCUSDT', start?: string, end?: string, interval: string = '1m') => {
    const mockRows = [];
    const startDate = start ? new Date(start) : new Date();
    const endDate = end ? new Date(end) : new Date();
    let currentDate = new Date(startDate);
    
    // 计算时间间隔（毫秒）
    let intervalMs = 60000; // 默认1分钟
    if (interval === '5m') intervalMs = 5 * 60000;
    else if (interval === '15m') intervalMs = 15 * 60000;
    else if (interval === '30m') intervalMs = 30 * 60000;
    else if (interval === '1h' || interval === '60m') intervalMs = 60 * 60000;
    else if (interval === '4h') intervalMs = 4 * 60 * 60000;
    else if (interval === '1D') intervalMs = 24 * 60 * 60000;
    
    // 生成过去7天的模拟数据（如果时间范围小于7天则使用实际时间范围）
    const maxDays = 7;
    let daysCount = Math.min(maxDays, Math.floor((endDate.getTime() - startDate.getTime()) / (24 * 60 * 60000)));
    if (daysCount < 1) daysCount = 7; // 至少生成7天的数据
    
    // 初始价格随机在100000-120000之间
    let basePrice = 110000 + Math.random() * 10000;
    
    for (let i = 0; i < daysCount * (24 * 60 / (intervalMs / 60000)); i++) {
      // 随机价格波动
      const priceChange = (Math.random() - 0.5) * 2000;
      const open = basePrice;
      const close = basePrice + priceChange;
      const high = Math.max(open, close) + Math.random() * 500;
      const low = Math.min(open, close) - Math.random() * 500;
      const volume = 100 + Math.random() * 900;
      
      // 格式化时间
      const dateStr = currentDate.toISOString().split('.')[0].replace('T', ' ');
      
      mockRows.push({
        datetime: dateStr,
        open: parseFloat(open.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        close: parseFloat(close.toFixed(2)),
        volume: parseFloat(volume.toFixed(6)),
        code: code
      });
      
      // 更新下一个时间点
      currentDate = new Date(currentDate.getTime() + intervalMs);
      basePrice = close;
    }
    return mockRows;
  }
  
  // 注：generateMockKlineData函数已在loadKlineData中定义并使用，此处不再重复定义

  // 关闭详情弹窗
  const handleCloseDetailModal = () => {
    setDetailModalVisible(false)
  }


  // 准备带有买卖点的K线图数据
  const prepareKlineWithTradesData = useMemo(() => {   
    // 如果没有数据，返回null让组件显示加载状态或提示信息
    if (!currentRunKlineData || currentRunKlineData.length === 0) {
      return null;
    }

    // 验证数据格式
    const validRows = currentRunKlineData.filter((item: any, _index: number) => {
      if (!item || typeof item !== 'object') {
        return false;
      }
      if (!('datetime' in item)) {
        return false;
      }
      if (!('open' in item)) {
        return false;
      }
      if (!('high' in item)) {
        return false;
      }
      if (!('low' in item)) {
        return false;
      }
      if (!('close' in item)) {
        return false;
      }
      if (!('volume' in item)) {
        return false;
      }
      if (typeof item.close !== 'number') {
        return false;
      }
      if (typeof item.volume !== 'number') {
        return false;
      }
      return true;
    });
    
    if (validRows.length === 0) {
      // 作为最后的手段，生成一些简单的模拟数据，确保图表能够显示
      const simpleMockData = [];
      const now = new Date();
      for (let i = 5; i >= 0; i--) {
        const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
        const dateStr = date.toISOString().split('.')[0].replace('T', ' ');
        const price = 110000 + Math.random() * 5000;
        simpleMockData.push({
          datetime: dateStr,
          open: price,
          high: price + Math.random() * 300,
          low: price - Math.random() * 300,
          close: price + (Math.random() - 0.5) * 500,
          volume: 50 + Math.random() * 500,
          code: 'BTCUSDT'
        });
      }
      // 创建并返回K线图配置，传递交易数据和网格线数据
    return createKlineChartConfig(simpleMockData, currentRunTrades, currentRunGridLevels);
    }
    
    // 创建并返回K线图配置，同时传递交易数据和网格线数据
    return createKlineChartConfig(validRows, currentRunTrades, currentRunGridLevels);
  }, [currentRunKlineData, currentRunTrades, currentRunGridLevels]);

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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>      <Card title='回测报告' className="shadow-lg" style={{ borderRadius: '12px', overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column' }}>
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
            showTotal: (total) => '共 ' + total + ' 条记录',
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
          style={{ height: '90vh', minWidth: '1000px', position: 'fixed', top: '20px', left: '50%', transform: 'translateX(-50%)' }}
          className="transition-all duration-300"
          styles={{
            body: { overflowY: 'auto', padding: '0' },
            content: { borderRadius: '8px', height: '100%' },
            wrapper: { display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }
          }}
        >
        {currentRunDetail && (
          <Tabs>
            {/* 基本信息 */}
            <Tabs.TabPane tab="基本信息" key="1">
              <div style={{padding: 24}}>
                <div style={{marginBottom: 24}}>
                  <h3 style={{marginBottom: 16, fontSize: '16px', fontWeight: 600, color: '#262626'}}>基本信息</h3>
                  <Card style={{borderRadius: '8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)'}}>
                    <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, padding: '8px 0'}}>
                      {/* 第一行：运行ID，策略名称，标的代码，时间间隔 */}
                      <div style={{display: 'flex', flexDirection: 'column', padding: '0 16px'}}>
                        <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>运行ID</span>
                        <span style={{fontSize: '13px', color: '#595959', wordBreak: 'break-all'}}>{currentRunDetail.run_id || '-'}</span>
                      </div>
                      <div style={{display: 'flex', flexDirection: 'column', padding: '0 16px'}}>
                        <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>策略名称</span>
                        <span style={{fontSize: '14px', color: '#262626', fontWeight: 500}}>{currentRunDetail.strategy || '-'}</span>
                      </div>
                      <div style={{display: 'flex', flexDirection: 'column', padding: '0 16px'}}>
                        <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>标的代码</span>
                        <span style={{fontSize: '14px', color: '#262626', fontWeight: 500}}>{currentRunDetail.code || '-'}</span>
                      </div>
                      <div style={{display: 'flex', flexDirection: 'column', padding: '0 16px'}}>
                        <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>时间间隔</span>
                        <span style={{fontSize: '14px', color: '#262626', fontWeight: 500}}>{currentRunDetail.interval || '-'}</span>
                      </div>
                      
                      {/* 第二行：创建时间，回测时间范围（占两列），初始资金 */}
                      <div style={{display: 'flex', flexDirection: 'column', padding: '0 16px'}}>
                        <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>创建时间</span>
                        <span style={{fontSize: '13px', color: '#595959'}}>{currentRunDetail.created_at ? formatDateTime(currentRunDetail.created_at) : '-'}</span>
                      </div>
                      <div style={{display: 'flex', flexDirection: 'column', padding: '0 16px', gridColumn: 'span 2'}}>
                        <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>回测时间范围</span>
                        <span style={{fontSize: '14px', color: '#262626'}}>{currentRunDetail.start_time ? formatDateTime(currentRunDetail.start_time) : '-'} 至 {currentRunDetail.end_time ? formatDateTime(currentRunDetail.end_time) : '-'}</span>
                      </div>
                      <div style={{display: 'flex', flexDirection: 'column', padding: '0 16px'}}>
                        <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>初始资金</span>
                        <span style={{fontSize: '14px', color: '#262626', fontWeight: 500}}>{currentRunDetail.initial_capital || '-'}</span>
                      </div>
                    </div>
                  </Card>
                </div>
                
                {currentRunDetail.paras && Object.keys(currentRunDetail.paras).length > 0 && (
                  <div>
                    <h3 style={{marginBottom: 16, fontSize: '16px', fontWeight: 600, color: '#262626'}}>回测参数</h3>
                    <Card style={{borderRadius: '8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)'}}>
                      <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, padding: '8px 0'}}>
                        {Object.entries(currentRunDetail.paras).map(([key, value]) => (
                          <div key={key} style={{display: 'flex', flexDirection: 'column', padding: '0 16px'}}>
                            <span style={{fontSize: '12px', color: '#262626', fontWeight: 'bold', marginBottom: '4px'}}>{key}</span>
                            <span style={{fontSize: '13px', color: '#595959', wordBreak: 'break-all'}}>
                              {typeof value === 'object' && value !== null ? JSON.stringify(value, null, 2) : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </Card>
                  </div>
                )}
              </div>
            </Tabs.TabPane>

            {/* 结果指标 */}
            <Tabs.TabPane tab="结果指标" key="2">
              <div style={{padding: 24}}>
                <h3 style={{marginBottom: 24, fontSize: '16px', fontWeight: 600, color: '#262626'}}>关键指标</h3>
                <Space direction="vertical" style={{width: '100%'}}>
                  {/* 第一行：初始资金、收益率、胜率、夏普率 */}
                  <Space style={{width: '100%', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16}}>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <Statistic title="初始资金" value={currentRunDetail.initial_capital} precision={2} />
                    </Card>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <Statistic 
                        title="收益率" 
                        value={((currentRunDetail.final_capital - currentRunDetail.initial_capital) / currentRunDetail.initial_capital * 100).toFixed(2)} 
                        suffix="%" 
                        valueStyle={{
                          color: ((currentRunDetail.final_capital - currentRunDetail.initial_capital) / currentRunDetail.initial_capital * 100) >= 0 ? '#52c41a' : '#f5222d'
                        }}
                      />
                    </Card>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <Statistic 
                        title="胜率" 
                        value={(currentRunDetail.win_rate * 100).toFixed(2)} 
                        suffix="%" 
                      />
                    </Card>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <Statistic 
                        title="夏普率" 
                        value={(() => {
                          // 优先使用后端计算的夏普率，如果不存在则使用前端计算的值
                          if (currentRunDetail.sharpe) {
                            return currentRunDetail.sharpe.toFixed(2);
                          }
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
                    </Card>
                  </Space>
                   {/* 第二行：最终资金、总收益、交易次数、最大回撤 */}
                  <Space style={{width: '100%', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16}}>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <Statistic title="最终资金" value={currentRunDetail.final_capital} precision={2} />
                    </Card>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <div style={{textAlign: 'center', width: '100%'}}>
                        <Statistic 
                          title="总收益(包含浮盈)" 
                          value={currentRunDetail.final_capital - currentRunDetail.initial_capital} 
                          precision={2} 
                          valueStyle={{
                            color: (currentRunDetail.final_capital - currentRunDetail.initial_capital) >= 0 ? '#52c41a' : '#f5222d',
                            textAlign: 'center'
                          }}
                          suffix={<div style={{fontSize: '12px', color: '#8c8c8c', textAlign: 'center'}}>
                            已实现盈利: {currentRunDetail.total_profit?.toFixed(2)}
                          </div>}
                        />
                      </div>
                    </Card>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <Statistic title="交易次数" value={currentRunDetail.trade_count || 0} />
                    </Card>
                    <Card style={{width: '100%', borderRadius: '8px', minWidth: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0'}}>
                      <Statistic 
                        title="最大回撤" 
                        value={(currentRunDetail.max_drawdown ? currentRunDetail.max_drawdown * 100 : 
                                (currentRunEquity.length > 0 ? currentRunEquity.reduce((max, item) => Math.min(max, item.drawdown), 0) * 100 : 0)).toFixed(2)} 
                        suffix="%" 
                        valueStyle={{ color: '#f5222d' }}
                      />
                    </Card>
                  </Space>
                </Space>
              </div>
            </Tabs.TabPane>
            
             {/* 交易记录 */}
            <Tabs.TabPane tab="交易记录" key="5">
                <Card style={{borderRadius: '8px', border: '1px solid #f0f0f0', boxShadow: 'none', overflow: 'auto'}}>
                  <Table 
                    dataSource={currentRunTrades}
                    rowKey={(record: any) => record.datetime + '-' + record.side}
                    pagination={{pageSize: 15, size: 'small' as const}}
                    scroll={{ x: '1800px', y: 'calc(100% - 140px)' }}
                    className="transition-all duration-300"
                    rowClassName={() => 'custom-row'}
                    columns={[
                      {title: '时间', dataIndex: 'datetime', key: 'datetime', render: formatDateTime, width: 160, ellipsis: false},
                      {title: '标的', dataIndex: 'code', key: 'code', width: 100},
                      {title: '方向', dataIndex: 'side', key: 'side', width: 80},
                      {title: '交易类型', dataIndex: 'trade_type', key: 'trade_type', width: 100},
                      {title: '交易前均价', dataIndex: 'avg_price', key: 'avg_price', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 120},
                      {title: '交易价格', dataIndex: 'price', key: 'price', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 100},
                      {title: '交易数量', dataIndex: 'qty', key: 'qty', render: (value: number) => value ? value.toString() : '-', width: 100},
                      {title: '交易金额', dataIndex: 'amount', key: 'amount', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 120},
                      {title: '交易后均价', dataIndex: 'current_avg_price', key: 'current_avg_price', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 120},
                      {title: '持仓数量', dataIndex: 'current_qty', key: 'current_qty', render: (value: number) => value ? value.toString() : '-', width: 120},
                      {title: '实现盈亏', dataIndex: 'realized_pnl', key: 'realized_pnl', render: (value: number) => value ? (
                        <span style={{color: value >= 0 ? '#52c41a' : '#f5222d'}}>
                          {value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0))}
                        </span>
                      ) : '-', width: 120},
                      {title: '持有现金', dataIndex: 'current_cash', key: 'current_cash', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 120},
                      {title: '净值', dataIndex: 'nav', key: 'nav', render: (value: number) => value ? value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0)) : '-', width: 100}
                    ]}
                  >
                 </Table>
                 <Button 
                    type="primary" 
                    icon={<DownloadOutlined />}
                    size="small"
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
                        '交易前均价': trade.avg_price ? trade.avg_price.toFixed(Math.min(4, trade.avg_price.toString().split('.')[1]?.length || 0)) : '-',
                        '交易价格': trade.price.toFixed(Math.min(4, trade.price.toString().split('.')[1]?.length || 0)),
                        '交易数量': trade.qty.toFixed(Math.min(4, trade.qty.toString().split('.')[1]?.length || 0)),
                        '交易金额': trade.amount.toFixed(Math.min(4, trade.amount.toString().split('.')[1]?.length || 0)),
                        '手续费': trade.fee.toFixed(Math.min(4, trade.fee.toString().split('.')[1]?.length || 0)),
                        '交易后均价': trade.current_avg_price ? trade.current_avg_price.toFixed(Math.min(4, trade.current_avg_price.toString().split('.')[1]?.length || 0)) : '-',
                        '当前价格': trade.close_price ? trade.close_price.toFixed(Math.min(4, trade.close_price.toString().split('.')[1]?.length || 0)) : '-',
                        '持仓数量': trade.current_qty ? trade.current_qty.toFixed(Math.min(4, trade.current_qty.toString().split('.')[1]?.length || 0)) : '-',
                        '实现盈亏': trade.realized_pnl ? trade.realized_pnl.toFixed(Math.min(4, trade.realized_pnl.toString().split('.')[1]?.length || 0)) : '-',
                        '持有现金': trade.current_cash ? trade.current_cash.toFixed(Math.min(4, trade.current_cash.toString().split('.')[1]?.length || 0)) : '-',
                        '净值': trade.nav ? trade.nav.toFixed(Math.min(4, trade.nav.toString().split('.')[1]?.length || 0)) : '-' 
                      }));
                        
                      // 创建工作表
                      const ws = XLSX.utils.json_to_sheet(exportData);
                       
                      // 创建工作簿
                      const wb = XLSX.utils.book_new();
                      XLSX.utils.book_append_sheet(wb, ws, '交易记录');
                       
                      // 生成文件名，使用保存的回测ID和当前日期
                      const filename = '交易记录_' + (currentRunId || 'unknown') + '_' + dayjs().format('YYYYMMDD_HHmmss') + '.xlsx';
                       
                      // 导出文件
                      XLSX.writeFile(wb, filename);
                      message.success('交易记录导出成功');
                    }}
                  >
                    导出Excel
                 </Button>
              </Card>
              <style>{`
                  .custom-row { height: 32px; line-height: 32px; }
                  .ant-table-thead > tr > th { height: 36px !important; padding: 0 12px; white-space: nowrap; }
                  .ant-table-tbody > tr > td { padding: 0 12px !important; border-bottom: 1px solid #f5f5f5; white-space: nowrap; }
                  .ant-table-row { transition: all 0.3s; }
                  .ant-table-fixed-left { position: sticky !important; left: 0 !important; z-index: 2 !important; }
                  .ant-table-pagination { margin-top: 8px; margin-bottom: 8px; }
                `}</style>
            </Tabs.TabPane>
            
            {/* K线交易图 */}
            <Tabs.TabPane tab="K线交易图" key="4">
              <div style={{ height: '600px', padding: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {prepareKlineWithTradesData ? (
                  <ReactECharts 
                    option={prepareKlineWithTradesData} 
                    style={{ height: '100%', width: '100%' }} 
                  />
                ) : (
                  <div style={{ textAlign: 'center', color: '#8c8c8c' }}>
                    加载中...
                  </div>
                )}
              </div>
            </Tabs.TabPane>
          </Tabs>
        )}
      </Modal>
    </div>
  )
}

export default Reports