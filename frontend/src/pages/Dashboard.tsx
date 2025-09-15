import React, { useState, useEffect, useMemo } from 'react';
import { Select, Button, Avatar } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, SearchOutlined, StarOutlined, ShareAltOutlined, DownloadOutlined, SettingOutlined, BarChartOutlined, LineChartOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import client from '../api/client';

// 计算移动平均线

// 解析CSV数据
const parseCSV = (csvString: string) => {
  const lines = csvString.split('\n');
  const result: { code: string; name: string; exchange: string; type: string }[] = [];
  
  // 跳过第一行标题行
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    
    const values = lines[i].split(',');
    if (values.length >= 2) {
      result.push({
        code: values[0],
        name: values[1],
        exchange: values[2] || '',
        type: values[3] || ''
      });
    }
  }
  
  return result;
};

// 使用fetch读取CSV文件
const fetchSymbolsFromCSV = async () => {
  try {
    const response = await fetch('/src/assets/symbols.csv');
    const csvText = await response.text();
    return parseCSV(csvText);
  } catch (error) {
    console.error('Failed to fetch symbols from CSV:', error);
    // 返回默认的模拟数据作为备用
    return [
      { code: 'AAPL', name: '苹果', exchange: 'NASDAQ', type: 'Stock' },
      { code: 'MSFT', name: '微软', exchange: 'NASDAQ', type: 'Stock' },
      { code: 'AMZN', name: '亚马逊', exchange: 'NASDAQ', type: 'Stock' },
    ];
  }
};

// 调用API获取candles数据
const fetchCandlesData = async (code: string, interval: string) => {
  try {
    const response = await client.get('/market/candles', {
      params: {
        code,
        interval
      }
    });
    return response.data.rows || [];
  } catch (error) {
    console.error('Failed to fetch candles data:', error);
    return [];
  }
};

// 调用API获取daily数据
const fetchDailyData = async (code: string, interval: string) => {
  try {
    const response = await client.get('/market/daily', {
      params: {
        code,
        interval
      }
    });
    return response.data.rows || [];
  } catch (error) {
    console.error('Failed to fetch daily data:', error);
    return [];
  }
};

// 格式化价格显示
const formatPrice = (value: number) => {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
};

const Dashboard: React.FC = () => {
  // 股票代码和名称
  const [symbol, setSymbol] = useState<string>('BTCUSDT');
  const [symbols, setSymbols] = useState<{ code: string; name: string; exchange: string; type: string }[]>([]);
  const [isLoadingSymbols, setIsLoadingSymbols] = useState<boolean>(true);
  
  // 时间周期
  const [timeframe, setTimeframe] = useState<string>('1D');
  
  // 加载symbol数据和市场概览数据
  useEffect(() => {
    const loadSymbols = async () => {
      setIsLoadingSymbols(true);
      try {
        const symbolsData = await fetchSymbolsFromCSV();
        setSymbols(symbolsData);
        // 如果有数据，设置第一个为默认选中
        if (symbolsData.length > 0 && !symbolsData.find(s => s.code === symbol)) {
          setSymbol(symbolsData[0].code);
        }
        // 加载市场概览数据
        await loadMarketOverview(symbolsData);
      } catch (error) {
        console.error('Error loading symbols:', error);
      } finally {
        setIsLoadingSymbols(false);
      }
    };
    
    loadSymbols();
  }, []);
  
  // 当时间周期变化时更新市场概览数据
  useEffect(() => {
    if (symbols.length > 0) {
      loadMarketOverview(symbols);
    }
  }, [timeframe]);
  
  // 调用API获取市场概览数据
  const loadMarketOverview = async (symbolsData: { code: string; name: string; exchange: string; type: string }[]) => {
    try {
      const overviewPromises = symbolsData.map(async (item) => {
        try {
          // 对于市场概览，我们只需要最新的数据点
          const response = await client.get('/market/candles', {
            params: {
              code: item.code,
              interval: timeframe,
              limit: 1 // 只获取最新的一个数据点
            }
          });
          
          if (response.data.rows && response.data.rows.length > 0) {
            const latestData = response.data.rows[0];
            const isUp = latestData.close >= latestData.open;
            const change = (latestData.close - latestData.open).toFixed(2);
            const changePercent = ((latestData.close - latestData.open) / latestData.open * 100).toFixed(2);
            
            return {
              id: item.code,
              code: item.code,
              name: item.name,
              price: formatPrice(latestData.close),
              change: change,
              changePercent: changePercent,
              trend: isUp ? 'up' : 'down'
            };
          } else {
            // 如果没有数据，返回基本信息
            return {
              id: item.code,
              code: item.code,
              name: item.name,
              price: '0.00',
              change: '0.00',
              changePercent: '0.00',
              trend: 'up'
            };
          }
        } catch (error) {
          console.error(`Failed to fetch market data for ${item.code}:`, error);
          // 出错时返回基本信息
          return {
            id: item.code,
            code: item.code,
            name: item.name,
            price: '0.00',
            change: '0.00',
            changePercent: '0.00',
            trend: 'up'
          };
        }
      });
      
      const overviewData = await Promise.all(overviewPromises);
      setMarketOverview(overviewData);
    } catch (error) {
      console.error('Failed to load market overview:', error);
    }
  };
  
  // 图表类型 - 修正类型定义，使用candlestick而不是candle
  const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick');
  
  // 时间范围选择
  const timeRanges = [
    { label: '1D', value: 1 },
    { label: '1W', value: 7 },
    { label: '1M', value: 30 },
    { label: '3M', value: 90 },
    { label: '1Y', value: 365 },
    { label: '5Y', value: 1825 },
    { label: 'ALL', value: 0 },
  ];
  const [selectedTimeRange, setSelectedTimeRange] = useState<number>(7);
  
  // 蜡烛图数据
  const [candleData, setCandleData] = useState<any[]>([]);
  
  // 市场概览数据
  const [marketOverview, setMarketOverview] = useState<any[]>([]);
  
  // 加载状态
  const [isLoading, setIsLoading] = useState<boolean>(false);
  
  // 处理时间范围变更
  const handleTimeRangeChange = (range: number) => {
    setSelectedTimeRange(range);
    
    // 根据时间范围设置默认时间周期
    switch(range) {
      case 1: // 1D
        setTimeframe('1m');
        break;
      case 7: // 1W
        setTimeframe('5m');
        break;
      case 30: // 1M
        setTimeframe('30m');
        break;
      case 90: // 3M
        setTimeframe('1h');
        break;
      case 365: // 1Y
        setTimeframe('1D');
        break;
      case 1825: // 5Y
        setTimeframe('1W');
        break;
      case 0: // ALL
        setTimeframe('1M');
        break;
      default:
        break;
    }
  };
  
  // 获取数据
  const fetchData = async () => {
    if (!symbol) return;
    
    setIsLoading(true);
    try {
      // 根据不同的时间周期调用不同的API
      if (['1m', '5m', '15m', '30m', '1h', '4h'].includes(timeframe)) {
        // 短期数据调用candles接口
        const data = await fetchCandlesData(symbol, timeframe);
        // 转换数据格式，确保isUp字段存在
        const formattedData = data.map((item: any) => ({
          ...item,
          isUp: item.close >= item.open
        }));
        setCandleData(formattedData);
      } else if (['1D', '1W', '1M'].includes(timeframe)) {
        // 长期数据调用daily接口
        const data = await fetchDailyData(symbol, timeframe);
        // 转换数据格式，确保isUp字段存在
        const formattedData = data.map((item: any) => ({
          ...item,
          isUp: item.close >= item.open
        }));
        setCandleData(formattedData);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setIsLoading(false);
    }
  };
  
  // 初始化数据和监听变化
  useEffect(() => {
    fetchData();
  }, [timeframe, selectedTimeRange, symbol]);
  
  // 图表配置
  const chartOption: EChartsOption = useMemo(() => {
    // 格式化时间轴标签
    const formatTime = (value: number | string) => {
      try {
        const date = new Date(value.toString());
        
        // 分钟级别的时间周期（1m,5m,15m,30m,60m,1h,4h）
        if (['1m', '5m', '15m', '30m', '60m', '1h', '4h'].includes(timeframe)) {
          return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
        }
        // 天级别的时间周期（1D,1W）
        else if (['1D', '1W'].includes(timeframe)) {
          return `${date.getMonth() + 1}/${date.getDate()}`;
        }
        // 月级别的时间周期（1M）
        else if (timeframe === '1M') {
          return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
        }
        return value;
      } catch (e) {
        return value;
      }
    };
    
    // 计算刻度间隔
    const calculateInterval = (count: number) => {
      // 根据数据量自动调节间隔
      if (count <= 30) return 3;
      if (count <= 50) return 5;
      if (count <= 100) return 10;
      if (count <= 200) return 20;
      if (count <= 500) return 50;
      return 100;
    };
    
    // 检测日期变化，用于添加纵向网格线
    
    // 获取日期变化位置，用于添加纵向网格线
    
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985'
          }
        },
        formatter: (params: any) => {
          let result = `${params[0].axisValue}<br/>`;
          params.forEach((param: any) => {
            if (param.seriesName === '成交量') {
              result += `${param.marker}${param.seriesName}: ${param.value.toLocaleString()}<br/>`;
            } else {
              result += `${param.marker}${param.seriesName}: ${formatPrice(param.value)}<br/>`;
            }
          });
          return result;
        }
      },
      legend: {
        data: ['K线', '成交量'],
        textStyle: {
          color: '#fff'
        },
        top: 10
      },
      grid: [
        {
          left: '10%',
          right: '10%',
          top: 40,
          height: '60%'
        },
        {
          left: '10%',
          right: '10%',
          top: '70%',
          height: '20%'
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: candleData.map(item => item.datetime),
          axisLine: { lineStyle: { color: '#4A4A6A' } },
          axisLabel: {
            color: '#8E8EA0',
            formatter: formatTime,
            interval: calculateInterval(candleData.length)
          },
          splitLine: { show: false },
          gridIndex: 0
        },
        {
          type: 'category',
          data: candleData.map(item => item.datetime),
          axisLine: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
          gridIndex: 1
        }
      ],
      yAxis: [
        {
          type: 'value',
          axisLine: { lineStyle: { color: '#4A4A6A' } },
          axisLabel: {
            color: '#8E8EA0',
            formatter: (value: number) => formatPrice(value)
          },
          splitLine: {
            lineStyle: {
              color: '#2E2E4A'
            }
          },
          scale: true,
          gridIndex: 0
        },
        {
          type: 'value',
          axisLine: { lineStyle: { color: '#4A4A6A' } },
          axisLabel: {
            color: '#8E8EA0',
            formatter: (value: number) => value.toLocaleString()
          },
          splitLine: {
            lineStyle: {
              color: '#2E2E4A'
            }
          },
          scale: true,
          gridIndex: 1
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 0,
          end: 100,
          filterMode: 'filter'
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          top: '90%',
          start: 0,
          end: 100,
          handleStyle: {
            color: '#8E8EA0'
          },
          textStyle: {
            color: '#8E8EA0'
          },
          backgroundColor: '#2E2E4A',
          fillerColor: '#4A4A6A',
          borderColor: '#1E1E2E'
        }
      ],
      series: [
        {
          name: chartType === 'candlestick' ? 'K线' : '价格',
          type: chartType,
          data: chartType === 'candlestick' 
            ? candleData.map(item => [item.open, item.close, item.low, item.high])
            : candleData.map(item => item.close),
          itemStyle: {
            color: '#52c41a',
            color0: '#ff4d4f',
            borderColor: '#52c41a',
            borderColor0: '#ff4d4f'
          },
          barWidth: '60%',
          xAxisIndex: 0,
          yAxisIndex: 0
        },
        {
          name: '成交量',
          type: 'bar',
          data: candleData.map(item => item.volume),
          itemStyle: {
            color: (params: any) => {
              const index = params.dataIndex;
              return candleData[index] && candleData[index].isUp ? '#52c41a' : '#ff4d4f';
            }
          },
          xAxisIndex: 1,
          yAxisIndex: 1
        }
      ]
    };
  }, [candleData, chartType, timeframe, formatPrice]);

  return (
    <div className="CFS-Quant-dashboard" style={{ minHeight: '100vh', backgroundColor: '#0F0F1A', margin: 0, padding: 0, paddingLeft: 240 }}>
      {/* 顶部工具栏 */}
      <div style={{ background: '#1E1E2E', padding: '8px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ color: '#fff', fontWeight: 'bold', fontSize: '16px' }}>CFS-Quant</div>
          
          <div style={{ display: 'flex', marginLeft: '32px' }}>
            <Select
              value={symbol}
              loading={isLoadingSymbols}
              style={{ width: 120, backgroundColor: '#2E2E4A', border: 'none', color: '#fff' }}
              onChange={(value) => setSymbol(value)}
              options={symbols.map(item => ({
                value: item.code,
                label: item.name
              }))}
              placeholder="加载中..."
            />
            
            <div style={{ marginLeft: '16px', color: '#fff', display: 'flex', alignItems: 'center' }}>
              {candleData.length > 0 ? (
                <>
                  <span style={{ marginRight: '8px' }}>{candleData[candleData.length - 1].close.toFixed(2)}</span>
                  <span style={{ 
                    color: candleData[candleData.length - 1].isUp ? '#52c41a' : '#ff4d4f', 
                    display: 'flex', 
                    alignItems: 'center' 
                  }}>
                    {candleData[candleData.length - 1].isUp ? 
                      <ArrowUpOutlined /> : <ArrowDownOutlined />}
                    {' '}{candleData[candleData.length - 1].isUp ? '+' : ''}{(candleData[candleData.length - 1].close - candleData[candleData.length - 1].open).toFixed(2)}
                    {' ('}{candleData[candleData.length - 1].isUp ? '+' : ''}{((candleData[candleData.length - 1].close - candleData[candleData.length - 1].open) / candleData[candleData.length - 1].open * 100).toFixed(2)}%)
                  </span>
                </>
              ) : (
                <span>加载中...</span>
              )}
            </div>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div className="ant-input-search ant-input-search-small" style={{ width: 200, backgroundColor: '#2E2E4A', border: 'none' }}>
            <input 
              type="search" 
              placeholder="搜索" 
              className="ant-input ant-input-sm ant-input-search-input" 
              style={{ backgroundColor: '#2E2E4A', border: 'none', color: '#fff' }}
            />
            <span className="ant-input-search-icon" style={{ color: '#8E8EA0' }}>
              <SearchOutlined />
            </span>
          </div>
          
          <Button
            type="text"
            icon={<StarOutlined style={{ color: '#fff' }} />
            }
            style={{ marginLeft: '16px', color: '#fff' }}
          />
          
          <Button
            type="text"
            icon={<ShareAltOutlined style={{ color: '#fff' }} />
            }
            style={{ marginLeft: '16px', color: '#fff' }}
          />
          
          <Button
            type="text"
            icon={<DownloadOutlined style={{ color: '#fff' }} />
            }
            style={{ marginLeft: '16px', color: '#fff' }}
          />
          
          <Button
            type="text"
            icon={<SettingOutlined style={{ color: '#fff' }} />
            }
            style={{ marginLeft: '16px', color: '#fff' }}
          />
          
          <Avatar style={{ marginLeft: '16px', backgroundColor: '#666' }}>TK</Avatar>
        </div>
      </div>
      
      {/* 主内容区域 */}
      <div style={{ display: 'flex', height: 'calc(100vh - 60px)', backgroundColor: '#0F0F1A' }}>
        {/* 左侧市场概览 - 固定宽度250px */}
        <div style={{ width: 250, backgroundColor: '#0F0F1A', padding: 8, overflow: 'auto', height: '100%', flexShrink: 0, position: 'relative', border: 'none' }}>
          <div style={{ color: '#8E8EA0', fontSize: '12px', marginBottom: 8 }}>市场概览</div>
          {marketOverview.length > 0 ? (
            marketOverview.map(item => (
              <div 
                key={item.id} 
                style={{ marginBottom: 12, padding: 8, backgroundColor: '#2E2E4A', borderRadius: 4, cursor: 'pointer' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#3E3E5A'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#2E2E4A'}
                onClick={() => setSymbol(item.code)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <div style={{ color: '#fff', fontWeight: 'bold' }}>{item.name}</div>
                  <div style={{ color: item.trend === 'up' ? '#52c41a' : '#ff4d4f', fontSize: '12px' }}
                       className={item.trend === 'up' ? 'up-trend' : 'down-trend'}>
                    {item.trend === 'up' ? '+' : ''}{item.changePercent}%
                  </div>
                </div>
                <div style={{ color: '#fff' }}>{item.price}</div>
                <div style={{ color: item.trend === 'up' ? '#52c41a' : '#ff4d4f', fontSize: '12px' }}
                     className={item.trend === 'up' ? 'up-trend' : 'down-trend'}>
                  {item.trend === 'up' ? '+' : ''}{item.change}
                </div>
              </div>
            ))
          ) : (
            <div style={{ color: '#8E8EA0', fontSize: '12px', textAlign: 'center', padding: 20 }}>
              加载市场数据中...
            </div>
          )}
        </div>
        
        {/* 右侧图表区域 - 占据剩余空间 */}
        <div style={{ flex: 1, padding: 4, display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' }}>
            {/* 图表控制区域 */}
            <div style={{ marginBottom: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              {/* 时间周期选择 - 移除限制，所有周期都可用 */}
              <div style={{ display: 'flex' }}>
                {['1m', '5m', '15m', '30m', '60m', '1h', '4h', '1D', '1W', '1M'].map((period) => (
                  <Button
                    key={period}
                    size="small"
                    onClick={() => setTimeframe(period)}
                    style={{
                      marginRight: '4px',
                      backgroundColor: timeframe === period ? '#26A69A' : '#2E2E4A',
                      border: 'none',
                      color: '#fff'
                    }}
                  >
                    {period}
                  </Button>
                ))}
              </div>
              
              {/* 图表类型选择 */}
              <div style={{ display: 'flex' }}>
                <Button
                  size="small"
                  icon={<BarChartOutlined />}
                  type={chartType === 'candlestick' ? 'primary' : 'default'}
                  onClick={() => setChartType('candlestick')}
                  style={{ marginRight: '4px', backgroundColor: chartType === 'candlestick' ? '#26A69A' : '#2E2E4A', border: 'none' }}
                />
                <Button
                  size="small"
                  icon={<LineChartOutlined />}
                  type={chartType === 'line' ? 'primary' : 'default'}
                  onClick={() => setChartType('line')}
                  style={{ marginRight: '4px', backgroundColor: chartType === 'line' ? '#26A69A' : '#2E2E4A', border: 'none' }}
                />
              </div>
              
              {/* 时间范围选择 */}
              <div style={{ display: 'flex' }}>
                {timeRanges.map((range) => (
                  <Button
                    key={range.value}
                    size="small"
                    onClick={() => handleTimeRangeChange(range.value)}
                    style={{
                      marginRight: '4px',
                      backgroundColor: selectedTimeRange === range.value ? '#26A69A' : '#2E2E4A',
                      border: 'none',
                      color: '#fff'
                    }}
                  >
                    {range.label}
                  </Button>
                ))}
              </div>
            </div>
            
            {/* 图表区域 - 自适应高度 */}
          
          {/* 图表区域 - 自适应高度 */}
          <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
            {isLoading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%', backgroundColor: '#0F0F1A' }}>
                <div style={{ color: '#fff' }}>加载中...</div>
              </div>
            ) : (
              <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;