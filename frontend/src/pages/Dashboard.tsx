import React, { useState, useEffect, useMemo } from 'react';
import { Select, Button, Avatar } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, SearchOutlined, StarOutlined, ShareAltOutlined, DownloadOutlined, SettingOutlined, BarChartOutlined, LineChartOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import client from '../api/client';
import { formatPriceWithUnit } from '../utils/priceFormatter';

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

// 调用API获取daily数据

// 格式化价格显示
const formatPrice = (value: number) => {
  return formatPriceWithUnit(value);
};

// 格式化成交量显示，根据值的大小显示K或M单位

const Dashboard: React.FC = () => {
  // 市场概览数据
  const [marketOverview, setMarketOverview] = useState<any[]>([]);
  // 当前选中股票的概览数据
  const [selectedSymbolData, setSelectedSymbolData] = useState<any>(null);
  // 图表数据
  const [candleData, setCandleData] = useState<any[]>([]);
  // 加载状态
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isLoadingSymbols, setIsLoadingSymbols] = useState<boolean>(false);
  // 股票列表
  const [symbols, setSymbols] = useState<any[]>([]);
  // 选中的股票
  const [symbol, setSymbol] = useState<string>('');
  // 时间周期
  const [timeframe, setTimeframe] = useState<string>('1D');
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
  
  // 当时间周期或symbol变化时更新市场概览数据
  useEffect(() => {
    if (symbols.length > 0) {
      loadMarketOverview(symbols);
    }
  }, [timeframe, symbol]);

  // 当市场概览数据或选中的symbol变化时，更新选中股票的概览数据
  useEffect(() => {
    if (marketOverview.length > 0 && symbol) {
      const symbolInfo = marketOverview.find(item => item.code === symbol);
      if (symbolInfo) {
        setSelectedSymbolData(symbolInfo);
      }
    }
  }, [marketOverview, symbol]);

  // 根据不同时间周期设置默认查询天数
  useEffect(() => {
    const daysMap: Record<string, number> = {
      '1m': 1,
      '5m': 1,
      '15m': 1,
      '30m': 1,
      '1h': 3,
      '4h': 7,
      '1D': 90,
      '1W': 365,
      '1M': 1825,
    };
    
    if (daysMap[timeframe]) {
      setSelectedTimeRange(daysMap[timeframe]);
    }
  }, [timeframe]);

  // 监听变化并获取数据
  useEffect(() => {
    if (symbol && selectedTimeRange !== undefined) {
      fetchData();
    }
  }, [symbol, selectedTimeRange, timeframe]);

  // 调用API获取市场概览数据 - 使用批量查询优化性能
  const loadMarketOverview = async (symbolsData: { code: string; name: string; exchange: string; type: string }[]) => {
    try {
      // 创建一个包含市场概览卡片symbol和选中symbol的集合，自动去重
      const uniqueSymbols = new Set<string>();
      
      // 添加市场概览卡片的所有symbol
      symbolsData.forEach(item => uniqueSymbols.add(item.code));
      
      // 添加被选择器选中的symbol（如果存在且不在市场概览卡片中）
      if (symbol && !symbolsData.find(item => item.code === symbol)) {
        uniqueSymbols.add(symbol);
      }
      
      // 转换为数组并连接
      const codes = Array.from(uniqueSymbols).join(',');
      
      // 调用批量查询API，获取最近2个bar的数据
      const response = await client.get('/market/batch-candles', {
        params: {
          codes: codes,
          interval: timeframe,
          limit: 2  // 获取最近2个bar的数据，用于计算更准确的价格变化百分比
        }
      });
      
      const batchData = response.data;
      
      // 处理批量数据，为每个股票创建概览信息
      const marketOverviewData = symbolsData.map(item => {
        const symbolData = batchData[item.code];
        
        if (symbolData) {
          // 确保数据是数组格式（可能返回多条记录）
          const dataArray = Array.isArray(symbolData) ? symbolData : [symbolData];
          
          // 如果有至少两个bar的数据，使用上一个bar的close作为基准计算变化
          if (dataArray.length >= 2) {
            // 按照时间排序，确保最新的数据在前
            const sortedData = [...dataArray].sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime());
            const latestBar = sortedData[0];
            const previousBar = sortedData[1];
            
            const isUp = latestBar.close >= previousBar.close;
            const change = (latestBar.close - previousBar.close).toFixed(2);
            const changePercent = ((latestBar.close - previousBar.close) / previousBar.close * 100).toFixed(2);
            
            return {
              id: item.code,
              code: item.code,
              name: item.name,
              price: latestBar.close,
              change: change,
              changePercent: changePercent,
              trend: isUp ? 'up' : 'down'
            };
          } else {
            // 只有一个bar的数据，使用开盘价和收盘价计算变化
            const latestBar = dataArray[0];
            const isUp = latestBar.close >= latestBar.open;
            const change = (latestBar.close - latestBar.open).toFixed(2);
            const changePercent = ((latestBar.close - latestBar.open) / latestBar.open * 100).toFixed(2);
            
            return {
              id: item.code,
              code: item.code,
              name: item.name,
              price: latestBar.close,
              change: change,
              changePercent: changePercent,
              trend: isUp ? 'up' : 'down'
            };
          }
        } else {
          // 如果没有数据，返回基本信息
          return {
            id: item.code,
            code: item.code,
            name: item.name,
            price: '-',
            change: '0.00',
            changePercent: '0.00',
            trend: 'neutral'
          };
        }
      });
      
      setMarketOverview(marketOverviewData);
    } catch (error) {
      console.error('批量获取市场概览数据失败:', error);
      
      // 出错时降级为单个查询模式，确保功能正常
      try {
        const overviewPromises = symbolsData.map(async (item) => {
          try {
            // 根据不同的时间周期调用不同的API
            let latestData = null;
            
            if (['1m', '5m', '15m', '30m', '1h', '4h'].includes(timeframe)) {
              const response = await client.get('/market/candles', {
                params: {
                  code: item.code,
                  interval: timeframe,
                  limit: 1
                }
              });
              latestData = response.data.rows && response.data.rows.length > 0 ? response.data.rows[0] : null;
            } else if (['1D', '1W', '1M'].includes(timeframe)) {
              const response = await client.get('/market/daily', {
                params: {
                  code: item.code,
                  interval: timeframe,
                  limit: 1
                }
              });
              latestData = response.data.rows && response.data.rows.length > 0 ? response.data.rows[0] : null;
            }
            
            if (latestData) {
              const isUp = latestData.close >= latestData.open;
              const change = (latestData.close - latestData.open).toFixed(2);
              const changePercent = ((latestData.close - latestData.open) / latestData.open * 100).toFixed(2);
              
              return {
                id: item.code,
                code: item.code,
                name: item.name,
                price: latestData.close,
                change: change,
                changePercent: changePercent,
                trend: isUp ? 'up' : 'down'
              };
            } else {
              return {
                id: item.code,
                code: item.code,
                name: item.name,
                price: '-',
                change: '0.00',
                changePercent: '0.00',
                trend: 'neutral'
              };
            }
          } catch (itemError) {
            console.error(`获取 ${item.code} 市场概览数据失败:`, itemError);
            return {
              id: item.code,
              code: item.code,
              name: item.name,
              price: '-',
              change: '0.00',
              changePercent: '0.00',
              trend: 'neutral'
            };
          }
        });
        
        const marketOverviewData = await Promise.all(overviewPromises);
        setMarketOverview(marketOverviewData);
      } catch (fallbackError) {
        console.error('降级获取市场概览数据也失败:', fallbackError);
      }
    }
  };

  // 处理时间范围变更
  const handleTimeRangeChange = (range: number) => {
    setSelectedTimeRange(range);
  };



  // 获取蜡烛图数据
  const fetchData = async () => {
    if (!symbol) return;
    
    setIsLoading(true);
    try {
      let response;
      if (['1m', '5m', '15m', '30m', '1h', '4h'].includes(timeframe)) {
        response = await client.get('/market/candles', {
          params: {
            code: symbol,
            interval: timeframe,
            limit: selectedTimeRange || 300
          }
        });
      } else if (['1D', '1W', '1M'].includes(timeframe)) {
        response = await client.get('/market/daily', {
          params: {
            code: symbol,
            interval: timeframe,
            limit: selectedTimeRange || 300
          }
        });
      }
      
      if (response && response.data && response.data.rows) {
        const processedData = response.data.rows.map((item: any) => ({
          ...item,
          isUp: item.close >= item.open
        }));
        setCandleData(processedData);
      }
    } catch (error) {
      console.error('获取K线数据失败:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // 格式化时间

  // 计算刻度间隔

  // 图表配置
  // 图表配置
  const chartOption = useMemo(() => {
    if (!candleData || candleData.length === 0) {
      // 提供默认的空图表配置，防止option为null/undefined
      return {
        backgroundColor: '#0F0F1A',
        title: {
          text: '暂无数据',
          textStyle: { color: '#fff' }
        },
        xAxis: [{ type: 'category', data: [], axisLine: { lineStyle: { color: '#4E4E6A' } }, axisLabel: { color: '#8E8EA0' } }],
        yAxis: [
          { type: 'value', axisLine: { lineStyle: { color: '#4E4E6A' } }, axisLabel: { color: '#8E8EA0' }, splitLine: { lineStyle: { color: '#2E2E4A' } } },
          { type: 'value', axisLine: { show: false }, axisLabel: { show: false }, splitLine: { show: false } }
        ],
        series: []
      };
    }

    // 准备数据
    const dates = candleData.map(item => {
      const date = new Date(item.datetime);
      if (['1m', '5m', '15m', '30m', '1h', '4h'].includes(timeframe)) {
        return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
      } else {
        return `${date.getMonth() + 1}/${date.getDate()}`;
      }
    });

    const candlestickData = candleData.map(item => [
      item.open,
      item.close,
      item.low,
      item.high
    ]);

    const lineData = candleData.map(item => item.close);

    // 格式化坐标轴的数值显示
    const axisLabelFormatter = (value: number) => {
      return formatPrice(value);
    };

    // 格式化成交量显示
    const formatVolume = (value: number) => {
      if (value >= 1000000) {
        return (value / 1000000).toFixed(2) + 'M';
      } else if (value >= 1000) {
        return (value / 1000).toFixed(2) + 'K';
      }
      return value.toString();
    };

    // 生成图表配置
    const option = {
      backgroundColor: '#0F0F1A',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 15, 26, 0.8)',
        borderColor: '#4E4E6A',
        textStyle: { color: '#fff' },
        axisPointer: {
          type: 'cross',
          lineStyle: { color: '#4E4E6A' }
        },
        formatter: function(params: any) {
          if (!params || params.length === 0) return '';
          
          let result = `${params[0].axisValue}<br/>`;
          if (chartType === 'candlestick') {
            result += `开: ${formatPrice(params[0].data[0])}<br/>`;
            result += `收: ${formatPrice(params[0].data[1])}<br/>`;
            result += `低: ${formatPrice(params[0].data[2])}<br/>`;
            result += `高: ${formatPrice(params[0].data[3])}<br/>`;
            // 添加成交量信息
            if (params.length > 1 && params[1].value) {
              result += `成交量: ${formatVolume(params[1].value)}`;
            }
          } else {
            result += `价格: ${formatPrice(params[0].value)}<br/>`;
            // 添加成交量信息
            if (params.length > 1 && params[1].value) {
              result += `成交量: ${formatVolume(params[1].value)}`;
            }
          }
          return result;
        }
      },
      grid: [
        { left: '5%', right: '2%', top: '5%', height: '60%' },
        { left: '5%', right: '2%', bottom: '5%', height: '20%' }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          axisLine: { lineStyle: { color: '#4E4E6A' } },
          axisLabel: { color: '#8E8EA0' },
          splitLine: { show: false },
          gridIndex: 0
        },
        {
          type: 'category',
          data: dates,
          axisLine: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
          gridIndex: 1
        }
      ],
      yAxis: [
        {
          type: 'value',
          position: 'left',
          axisLine: { lineStyle: { color: '#4E4E6A' } },
          axisLabel: { color: '#8E8EA0', formatter: axisLabelFormatter },
          splitLine: { lineStyle: { color: '#2E2E4A' } },
          scale: true,
          gridIndex: 0
        },
        {
          type: 'value',
          position: 'left',
          axisLine: { show: false },
          axisLabel: { color: '#8E8EA0', formatter: formatVolume },
          splitLine: { show: false },
          scale: true,
          gridIndex: 1
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 0,
          end: 100
        },
        {
          type: 'slider',
          xAxisIndex: [0, 1],
          bottom: 10,
          height: 20,
          borderColor: '#4E4E6A',
          backgroundColor: '#1E1E2E',
          fillerColor: 'rgba(38, 166, 154, 0.2)',
          handleStyle: { color: '#26A69A' },
          textStyle: { color: '#8E8EA0' },
          start: 0,
          end: 100
        }
      ],
      series: [
        // K线图/折线图系列
        {
          name: chartType === 'candlestick' ? 'K线图' : '折线图',
          type: chartType,
          data: chartType === 'candlestick' ? candlestickData : lineData,
          smooth: chartType === 'line',
          itemStyle: {
            color: '#52c41a',
            color0: '#ff4d4f',
            borderColor: '#52c41a',
            borderColor0: '#ff4d4f'
          },
          lineStyle: {
            color: '#26A69A'
          },
          xAxisIndex: 0,
          yAxisIndex: 0
        },
        // 成交量柱状图系列
        {
          name: '成交量',
          type: 'bar',
          data: candleData.map(item => item.volume || 0),
          itemStyle: {
            color: function(params: any) {
              // 根据K线的涨跌设置成交量柱子的颜色
              const isUp = candleData[params.dataIndex] && candleData[params.dataIndex].isUp !== undefined ? 
                           candleData[params.dataIndex].isUp : true;
              return isUp ? '#52c41a' : '#ff4d4f';
            }
          },
          xAxisIndex: 1,
          yAxisIndex: 1
        }
      ]
    };

    return option;
  }, [candleData, chartType, timeframe, formatPrice]);

  return (
    <div className="CFS-Quant-dashboard" style={{ minHeight: '100vh', backgroundColor: '#0F0F1A', margin: 0, padding: 0 }}>
      {/* 顶部工具栏 - 紧凑布局 */}
      <div style={{ background: '#1E1E2E', padding: '4px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: 'none', height: '45px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ color: '#fff', fontWeight: 'bold', fontSize: '16px' }}>CFS-Quant</div>
          
          <div style={{ display: 'flex', marginLeft: '16px' }}>
            <Select
              value={symbol}
              loading={isLoadingSymbols}
              style={{ width: 120, backgroundColor: '#2E2E4A', border: 'none', color: '#fff' }}
              onChange={(value) => {
                setSymbol(value);
                // 从市场概览数据中查找并设置选中symbol的详细信息
                const symbolInfo = marketOverview.find(item => item.code === value);
                if (symbolInfo) {
                  setSelectedSymbolData(symbolInfo);
                }
              }}
              options={symbols.map(item => ({
                value: item.code,
                label: item.name
              }))}
              placeholder="加载中..."
            />
            
            <div style={{ marginLeft: '8px', color: '#fff', display: 'flex', alignItems: 'center' }}>
              {selectedSymbolData ? (
                <>
                  <span style={{ marginRight: '8px' }}>{selectedSymbolData.price}</span>
                  <span style={{ 
                    color: selectedSymbolData.trend === 'up' ? '#52c41a' : '#ff4d4f', 
                    display: 'flex', 
                    alignItems: 'center' 
                  }}>
                    {selectedSymbolData.trend === 'up' ? 
                      <ArrowUpOutlined /> : <ArrowDownOutlined />}
                    {' '}{selectedSymbolData.trend === 'up' ? '+' : ''}{selectedSymbolData.change}
                    {' ('}{selectedSymbolData.trend === 'up' ? '+' : ''}{selectedSymbolData.changePercent}%)
                  </span>
                </>
              ) : candleData.length > 0 ? (
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
              icon={<StarOutlined style={{ color: '#fff' }} />}
              style={{ marginLeft: '16px', color: '#fff' }}
            />
          
          <Button
            type="text"
            icon={<ShareAltOutlined style={{ color: '#fff' }} />}
            style={{ marginLeft: '16px', color: '#fff' }}
          />
          
          <Button
            type="text"
            icon={<DownloadOutlined style={{ color: '#fff' }} />}
            style={{ marginLeft: '16px', color: '#fff' }}
          />
          
          <Button
            type="text"
            icon={<SettingOutlined style={{ color: '#fff' }} />}
            style={{ marginLeft: '16px', color: '#fff' }}
          />
          
          <Avatar style={{ marginLeft: '16px', backgroundColor: '#666' }}>TK</Avatar>
        </div>
      </div>
      
      {/* 主内容区域 */}
      <div style={{ display: 'flex', height: 'calc(100vh - 55px)', backgroundColor: '#0F0F1A' }}>
        {/* 左侧市场概览 - 减小宽度 */}
        <div style={{ width: 180, backgroundColor: '#0F0F1A', padding: 4, overflow: 'auto', height: '100%', flexShrink: 0, position: 'relative', border: 'none' }}>
          <div style={{ color: '#8E8EA0', fontSize: '12px', marginBottom: 8 }}>市场概览</div>
          {marketOverview.length > 0 ? (
            marketOverview.map(item => (
              <div 
                key={item.id} 
                style={{ 
                  marginBottom: 12, 
                  padding: 8, 
                  backgroundColor: symbol === item.code ? '#3E3E5A' : '#2E2E4A', 
                  borderRadius: 4, 
                  cursor: 'pointer' 
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#3E3E5A'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = symbol === item.code ? '#3E3E5A' : '#2E2E4A'}
                onClick={() => {
                  setSymbol(item.code);
                  setSelectedSymbolData(item);
                }}
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
        <div style={{ flex: 1, padding: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' }}>
            {/* 图表控制区域 - 紧凑布局 */}
            <div style={{ marginBottom: 0, display: 'flex', alignItems: 'center', padding: '1px 2px', height: '30px' }}>
              {/* 时间周期选择 - 移除限制，所有周期都可用 */}
              <div style={{ display: 'flex', marginRight: 'auto' }}>
                {['1m', '5m', '15m', '30m', '60m', '1h', '4h', '1D', '1W', '1M'].map((period) => (
                  <Button
                    key={period}
                    size="small"
                    onClick={() => setTimeframe(period)}
                    style={{
                      marginRight: '2px',
                      padding: '2px 6px',
                      backgroundColor: timeframe === period ? '#26A69A' : '#2E2E4A',
                      border: 'none',
                      color: '#fff',
                      fontSize: '11px'
                    }}
                  >
                    {period}
                  </Button>
                ))}
              </div>
              
              {/* 图表类型选择和显示控制 - 使用相对定位调整位置 */}
              <div style={{ display: 'flex', justifyContent: 'center', flex: 1, position: 'relative', left: '-55px' }}>
                <Button
                  size="small"
                  icon={<BarChartOutlined />}
                  type={chartType === 'candlestick' ? 'primary' : 'default'}
                  onClick={() => setChartType('candlestick')}
                  style={{ marginRight: '2px', padding: '2px 4px', backgroundColor: chartType === 'candlestick' ? '#26A69A' : '#2E2E4A', border: 'none' }}
                />
                <Button
                  size="small"
                  icon={<LineChartOutlined />}
                  type={chartType === 'line' ? 'primary' : 'default'}
                  onClick={() => setChartType('line')}
                  style={{ marginRight: '8px', padding: '2px 4px', backgroundColor: chartType === 'line' ? '#26A69A' : '#2E2E4A', border: 'none' }}
                />
              </div>
              
              {/* 时间范围选择 */}
              <div style={{ display: 'flex', marginLeft: 'auto' }}>
                {timeRanges.map((range) => (
                  <Button
                    key={range.value}
                    size="small"
                    onClick={() => handleTimeRangeChange(range.value)}
                    style={{
                      marginRight: '2px',
                      padding: '2px 6px',
                      backgroundColor: selectedTimeRange === range.value ? '#26A69A' : '#2E2E4A',
                      border: 'none',
                      color: '#fff',
                      fontSize: '11px'
                    }}
                  >
                    {range.label}
                  </Button>
                ))}
              </div>
            </div>
            
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