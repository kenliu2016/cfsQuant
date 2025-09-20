
import { useEffect, useState, useMemo, useCallback } from 'react'
import { Card, Form, Select, DatePicker, Tabs, Spin } from 'antd'
import client from '../api/client'
import dayjs from 'dayjs'
import ReactECharts from 'echarts-for-react'
import { formatPriceWithUnit } from '../utils/priceFormatter'

const { RangePicker } = DatePicker

type Row = { datetime: string; open:number; high:number; low:number; close:number; volume:number }

// 计算移动平均线
const calculateMA = (data: Row[], dayCount: number): (number | null)[] => {
  const result: (number | null)[] = []
  for (let i = 0, len = data.length; i < len; i++) {
    if (i < dayCount - 1) {
      result.push(null)
      continue
    }
    let sum = 0
    for (let j = 0; j < dayCount; j++) {
      sum += data[i - j].close
    }
    result.push(Number((sum / dayCount).toFixed(2)))
  }
  return result
}

export default function Market() {
  const [form] = Form.useForm()
  const [daily, setDaily] = useState<Row[]>([])
  const [intraday, setIntraday] = useState<Row[]>([])
  const [activeTab, setActiveTab] = useState('daily') // 默认选中日线图
  const [symbols, setSymbols] = useState<{ value: string; label: string }[]>([])
  const [filteredSymbols, setFilteredSymbols] = useState<{ value: string; label: string }[]>([])
  const [isDailyLoading, setIsDailyLoading] = useState(false) // 日线图加载状态
  const [isIntradayLoading, setIsIntradayLoading] = useState(false) // 分时图加载状态

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

  // 设置默认时间范围
  const setDefaultTimeRange = (tabType: string) => {
    const today = dayjs().startOf('day')
    
    if (tabType === 'daily') {
      // 日线图：最近一个月
      const startDate = today.add(-1, 'month')
      form.setFieldsValue({
        timeRange: [startDate, today]
      })
    } else if (tabType === 'rt') {
      // 分时图：最近两天
      const startDate = today.add(-1, 'day')
      form.setFieldsValue({
        timeRange: [startDate, today]
      })
    }
  }

  // 当标签页切换时自动设置时间范围并加载数据
  const handleTabChange = async (key: string) => {
    setActiveTab(key)
    setDefaultTimeRange(key)
    
    // 等待表单值更新后再加载数据
    setTimeout(() => {
      if (key === 'daily') {
        fetchDaily()
      } else if (key === 'rt') {
        fetchIntraday()
      }
    }, 100)
  }

  useEffect(() => {
    // 初始化时加载标的数据
    loadSymbols();
  }, [])

  useEffect(() => {
    // 当标的数据加载完成后设置默认值
    if (symbols.length > 0) {
      form.setFieldsValue({
        code: 'BTCUSDT'
      })
      
      // 设置默认时间范围并加载数据
      setDefaultTimeRange(activeTab)
      setTimeout(() => {
        if (activeTab === 'daily') {
          fetchDaily()
        } else if (activeTab === 'rt') {
          fetchIntraday()
        }
      }, 100)
    }
  }, [symbols, activeTab])

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

  const fetchDaily = async () => {
    try {
      setIsDailyLoading(true)
      const v = await form.validateFields()
      const [start, end] = v.timeRange
      // 日线图不需要额外的时分秒信息
      const res = await client.get('/market/daily', {
        params: {
          code: v.code,
          start: start.format('YYYY-MM-DD HH:mm:ss'),
          end: end.format('YYYY-MM-DD HH:mm:ss')
        }
      })
      setDaily(res.data.rows || [])
    } catch (error) {
      console.error('获取日线数据失败:', error)
    } finally {
      setIsDailyLoading(false)
    }
  }

  const fetchIntraday = async () => {
    try {
      setIsIntradayLoading(true)
      const v = await form.validateFields()
      let [start, end] = v.timeRange
      
      // 分时图自动添加时分秒信息：前一天00:00:00到当天23:59:00
      start = start.startOf('day')
      end = end.endOf('day')
      
      const res = await client.get('/market/intraday', {
        params: {
          code: v.code,
          start: start.format('YYYY-MM-DD HH:mm:ss'),
          end: end.format('YYYY-MM-DD HH:mm:ss')
        }
      })
      setIntraday(res.data.rows || [])
    } catch (error) {
      console.error('获取分时数据失败:', error)
    } finally {
      setIsIntradayLoading(false)
    }
  }
  
  // 添加防抖功能，避免频繁请求
  const debounce = (func: Function, delay: number) => {
    let timeoutId: ReturnType<typeof setTimeout>;
    return (...args: any[]) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => func.apply(null, args), delay);
    };
  };

  // 防抖版本的数据加载函数
  const debouncedFetchDaily = debounce(fetchDaily, 500);
  const debouncedFetchIntraday = debounce(fetchIntraday, 500);

  // 当时间范围或代码变更时自动重新加载数据
  const handleTimeRangeChange = (changedValues: any) => {
    // 只在时间范围或代码改变时触发重新加载
    if (changedValues.timeRange || changedValues.code) {
      if (activeTab === 'daily') {
        debouncedFetchDaily();
      } else if (activeTab === 'rt') {
        debouncedFetchIntraday();
      }
    }
  };

  // 使用useMemo缓存价格范围计算结果，避免每次渲染都重新计算
  const priceRange = useMemo(() => {
    if (daily.length === 0) return { min: 0, max: 10000 }
    
    // 优化计算：单次遍历找到最值
    let minPrice = Infinity
    let maxPrice = -Infinity
    
    for (let i = 0; i < daily.length; i++) {
      const row = daily[i]
      minPrice = Math.min(minPrice, row.open, row.close, row.low, row.high)
      maxPrice = Math.max(maxPrice, row.open, row.close, row.low, row.high)
    }
    
    const margin = (maxPrice - minPrice) * 0.05 // 5%的边距
    
    return { 
      min: minPrice - margin, 
      max: maxPrice + margin 
    }
  }, [daily])
  
  // 使用useMemo缓存分时图价格范围计算结果
  const intradayPriceRange = useMemo(() => {
    if (intraday.length === 0) return { min: 0, max: 10000 }
    
    // 优化计算：单次遍历找到最值
    let minPrice = Infinity
    let maxPrice = -Infinity
    
    for (let i = 0; i < intraday.length; i++) {
      const price = intraday[i].close
      minPrice = Math.min(minPrice, price)
      maxPrice = Math.max(maxPrice, price)
    }
    
    const margin = (maxPrice - minPrice) * 0.03 // 3%的边距
    
    return { 
      min: minPrice - margin, 
      max: maxPrice + margin 
    }
  }, [intraday])
  
  // 使用useCallback缓存价格格式化函数，统一调用工具函数
  const formatPrice = useCallback((value: number) => {
    return formatPriceWithUnit(value);
  }, []);
  
  // 使用useMemo缓存图表配置对象，避免每次渲染都重新创建
    const candleOption = useMemo(() => {
      // 预计算图表需要的数据，避免在配置对象中多次map
      const dateTimes = []
      const candlestickData = []
      const volumeData = []
      
      for (let i = 0; i < daily.length; i++) {
        const row = daily[i]
        dateTimes.push(row.datetime)
        candlestickData.push([row.open, row.close, row.low, row.high])
        volumeData.push(row.volume)
      }
      
      // 计算5日、10日和20日均线
      const ma5 = calculateMA(daily, 5)
      const ma10 = calculateMA(daily, 10)
      const ma20 = calculateMA(daily, 20)
      
      return {
        tooltip: { trigger: 'axis' },
        axisPointer: { type: 'cross' },
        legend: {
          data: ['K', '5日均线', '10日均线', '20日均线', 'Volume'],
          top: 10
        },
        xAxis: [
          {
            type: 'category', 
            data: dateTimes, 
            scale: true,
            axisLabel: {
              formatter: (value: string) => {
                // 日线图横坐标显示月-日
                return dayjs(value).format('MM-DD');
              },
              show: true, // 确保刻度可见
              color: '#333', // 设置刻度颜色
              rotate: 45, // 旋转标签避免重叠
              interval: (_index: number) => {
                // 简化的间隔逻辑，确保至少有刻度显示
                const totalPoints = daily.length;
                if (totalPoints === 0) return false;
                if (totalPoints <= 10) return 0; // 显示所有
                if (totalPoints <= 30) return Math.floor(totalPoints / 10);
                if (totalPoints <= 60) return Math.floor(totalPoints / 20);
                return Math.floor(totalPoints / 30);
              }
            },
            axisLine: { show: true }, // 显示坐标轴轴线
            axisTick: { show: true } // 显示坐标轴刻度
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
            scale: true,
            min: priceRange.min,
            max: priceRange.max,
            axisLabel: {
              formatter: formatPrice,
              interval: 'auto' // 自动调整纵坐标刻度间隔
            }
          }, 
          {
            gridIndex:1,
            axisLabel: {
              formatter: formatPrice,
              interval: 'auto' // 自动调整交易量纵坐标刻度间隔
            }
          }
        ],
        grid:[{ left:40, right:20, height: '55%' }, { left:40, right:20, top: '65%', height: '20%' }],
        series: [
          {
            type:'candlestick', 
            name:'K', 
            data: candlestickData,
            itemStyle: {
              color: '#ef232a',
              color0: '#14b143',
              borderColor: '#ef232a',
              borderColor0: '#14b143'
            }
          },
          {
            type:'line', 
            name:'5日均线', 
            data: ma5, 
            smooth: true, 
            lineStyle: { color: '#ff9900', width: 1.5 },
            showSymbol: false
          },
          {
            type:'line', 
            name:'10日均线', 
            data: ma10, 
            smooth: true, 
            lineStyle: { color: '#0099ff', width: 1.5 },
            showSymbol: false
          },
          {
            type:'line', 
            name:'20日均线', 
            data: ma20, 
            smooth: true, 
            lineStyle: { color: '#ff00ff', width: 1.5 },
            showSymbol: false
          },
          { type:'bar', name:'Volume', xAxisIndex:1, yAxisIndex:1, data: volumeData }
        ],
        // 开启ECharts性能优化
        animation: false,
        animationThreshold: 2000
      }
    }, [daily, priceRange, formatPrice, calculateMA])

  // 使用useMemo缓存markLines计算结果
  const markLines = useMemo(() => {
    if (!intraday || intraday.length <= 1) return [];
    
    const result = [];
    // 优化：只提取日期部分进行比较，避免重复调用dayjs
    let prevDateStr = intraday[0].datetime.slice(0, 10); // 假设格式为YYYY-MM-DD HH:mm:ss
    
    // 遍历数据，查找跨天的点
    for (let i = 1; i < intraday.length; i++) {
      const currDateStr = intraday[i].datetime.slice(0, 10);
      if (currDateStr !== prevDateStr) {
        // 在跨天的位置添加虚线标记
        result.push({
          xAxis: intraday[i].datetime,
          lineStyle: {
            type: 'dashed',
            color: '#999',
            width: 1
          }
        });
        prevDateStr = currDateStr;
      }
    }
    
    return result;
  }, [intraday]);
  
  // 使用useMemo缓存分时图配置对象
  const lineOption = useMemo(() => {
    // 预计算图表需要的数据
    const dateTimes = []
    const candlestickData = []
    const volumeData = []
    
    for (let i = 0; i < intraday.length; i++) {
      const row = intraday[i]
      dateTimes.push(row.datetime)
      candlestickData.push([row.open, row.close, row.low, row.high])
      volumeData.push(row.volume)
    }
    
    // 计算交易量的5日和10日均线
    const volMA5 = calculateMA(intraday, 5)
    const volMA10 = calculateMA(intraday, 10)
    
    // 生成graphic配置
    const graphicElements = markLines.map((markLine, _index) => ({
      type: 'line',
      shape: {
        x1: markLine.xAxis,
        y1: 0,
        x2: markLine.xAxis,
        y2: 1
      },
      style: {
        stroke: markLine.lineStyle.color,
        lineWidth: markLine.lineStyle.width,
        lineDash: [5, 5]
      },
      bounding: 'raw',
      left: '0%',
      top: '0%',
      width: '100%',
      height: '100%'
    }));
    
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const timeData = params[0]
          const volData = params[1]
          const volMA5Data = params[2]
          const volMA10Data = params[3]
          // 根据开盘价和当前价格计算涨跌幅
          const openPrice = intraday.length > 0 ? intraday[0].open : 0
          const currentPrice = timeData.value[1] // close价格
          const change = currentPrice - openPrice
          const changePercent = openPrice > 0 ? (change / openPrice) * 100 : 0
          const color = change >= 0 ? '#ef232a' : '#14b143'
          
          return `
            <div style="text-align: left;">
              <div>${timeData.name}</div>
              <div>开盘: ${formatPrice(timeData.value[0])}</div>
              <div>收盘: ${formatPrice(timeData.value[1])}</div>
              <div>最低: ${formatPrice(timeData.value[2])}</div>
              <div>最高: ${formatPrice(timeData.value[3])}</div>
              <div style="color: ${color};">
                涨跌额: ${formatPrice(change)} (${changePercent.toFixed(2)}%)
              </div>
              <div>成交量: ${volData.value}</div>
              <div>5日量均: ${volMA5Data.value}</div>
              <div>10日量均: ${volMA10Data.value}</div>
            </div>
          `
        }
      },
      legend: {
        data: ['K线', '成交量', '5日量均', '10日量均'],
        top: 10
      },
      graphic: graphicElements,
      xAxis: [
        {
          type: 'category', 
          data: dateTimes,
          axisLabel: {
            formatter: (value: string) => {
              // 分时图横坐标只显示小时 - 优化：提取时间部分而非完整解析
              return value.slice(11, 13); // 假设格式为YYYY-MM-DD HH:mm:ss
            },
            show: true, // 确保刻度可见
            color: '#333', // 设置刻度颜色
            rotate: 0, // 不旋转标签，小时显示更加清晰
            interval: (index: number) => {
              const totalPoints = intraday.length;
              if (totalPoints === 0) return false;
              
              // 根据数据量动态调整间隔
              if (totalPoints > 300) return index % Math.ceil(totalPoints / 8) === 0;  // 数据量极大时，显示更少的点
              if (totalPoints > 150) return index % Math.ceil(totalPoints / 12) === 0; // 数据量大时，减少密度
              if (totalPoints > 80) return index % Math.ceil(totalPoints / 18) === 0;  // 数据量中等时，适中密度
              return index % Math.ceil(totalPoints / 24) === 0;  // 数据量少时，保持适当密度
            }
          },
          axisLine: { show: true }, // 显示坐标轴轴线
          axisTick: { show: true } // 显示坐标轴刻度
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
          scale: true,
          min: intradayPriceRange.min,
          max: intradayPriceRange.max,
          axisLabel: {
            formatter: formatPrice,
            interval: 'auto' // 自动调整纵坐标刻度间隔
          }
        }, 
        {
          gridIndex:1,
          axisLabel: {
            formatter: formatPrice,
            interval: 'auto' // 自动调整交易量纵坐标刻度间隔
          }
        }
      ],
      grid:[{ left:40, right:20, height: '55%' }, { left:40, right:20, top: '65%', height: '20%' }],
      series: [
        { 
          type:'candlestick', 
          name:'K线', 
          data: candlestickData,
          itemStyle: {
            color: '#ef232a',
            color0: '#14b143',
            borderColor: '#ef232a',
            borderColor0: '#14b143'
          }
        },
        { 
          type:'bar', 
          name:'成交量', 
          xAxisIndex:1, 
          yAxisIndex:1, 
          data: volumeData,
          itemStyle: {
            color: '#14b143'
          } 
        },
        { 
          type:'line', 
          name:'5日量均', 
          xAxisIndex:1, 
          yAxisIndex:1, 
          data: volMA5, 
          smooth: true, 
          lineStyle: { color: '#ff9900', width: 1.5 },
          showSymbol: false
        },
        { 
          type:'line', 
          name:'10日量均', 
          xAxisIndex:1, 
          yAxisIndex:1, 
          data: volMA10, 
          smooth: true, 
          lineStyle: { color: '#0099ff', width: 1.5 },
          showSymbol: false
        }
      ],
      // 开启ECharts性能优化
      animation: false,
      animationThreshold: 2000
    }
  }, [intraday, markLines, intradayPriceRange, formatPrice, calculateMA])

  return (
    <Card title="Market 行情">
      <Form form={form} layout="inline" onValuesChange={handleTimeRangeChange}>
        <Form.Item name="code" label="标的" rules={[{required:true}]}>
          <Select
            placeholder="请选择或输入标的"
            style={{width: 220}}
            showSearch
            filterOption={false}
            onSearch={handleSymbolSearch}
            options={filteredSymbols}
          />
        </Form.Item>
        <Form.Item name="timeRange" label="时间范围" rules={[{required:true}]}>
          {/* 简化的时间选择器，只选择年月日 */}
          <RangePicker />
        </Form.Item>
      </Form>

      <div style={{ marginTop: 0, padding: 0 }}>
        <Tabs 
          activeKey={activeTab}
          onChange={handleTabChange}
          items={[
            { key:'daily', label:'日线图', children: (
              <Spin spinning={isDailyLoading} tip="加载中..." style={{minHeight: 550}}>
                <ReactECharts option={candleOption} style={{height: 550}}/>
              </Spin>
            ) },
            { key:'rt', label:'分时图', children: (
              <Spin spinning={isIntradayLoading} tip="加载中..." style={{minHeight: 550}}>
                <ReactECharts option={lineOption} style={{height: 550}}/>
              </Spin>
            ) }
          ]} 
        />
      </div>
    </Card>
  )
}
