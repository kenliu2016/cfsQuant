import React, { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Tabs, Statistic, Table, Button, Space, message, Spin } from 'antd';
import dayjs from 'dayjs';
import * as XLSX from 'xlsx';
import { DownloadOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import client from '../api/client';

const { TabPane } = Tabs;

// 定义交易信号类型
interface TradeSignal {
  datetime: number;
  count: number;
  side: 'buy' | 'sell' | 'unknown';
}

// 定义网格级别类型
interface GridLevel {
  name: string;
  price: number;
}

const ReportDetail: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [loading, setLoading] = useState(true);
  const [currentRunId, setCurrentRunId] = useState<string>('')
  const [currentRunDetail, setCurrentRunDetail] = useState<any>({});
  const [currentRunTrades, setCurrentRunTrades] = useState<any[]>([]);
  const [currentRunKlineData, setCurrentRunKlineData] = useState<any[]>([]);
  const [currentRunEquity, setCurrentRunEquity] = useState<any[]>([]);
  const [currentRunGridLevels, setCurrentRunGridLevels] = useState<GridLevel[]>([]);

  // 格式化日期时间 - 增强版，支持多种时间格式
  const formatDateTime = (timestamp: any) => {
    if (!timestamp || timestamp === 'Invalid date') return '-';
    
    // 尝试多种转换方式
    let date;
    
    // 如果是数字，直接使用
    if (typeof timestamp === 'number' && !isNaN(timestamp)) {
      date = dayjs(timestamp);
    }
    // 如果是字符串，尝试解析
    else if (typeof timestamp === 'string') {
      date = dayjs(timestamp);
      // 如果解析失败，尝试当作时间戳解析
      if (!date.isValid()) {
        const numTimestamp = Number(timestamp);
        if (!isNaN(numTimestamp)) {
          date = dayjs(numTimestamp);
        }
      }
    }
    // 其他类型，尝试转换
    else {
      date = dayjs(timestamp);
    }
    
    return date.isValid() ? date.format('YYYY-MM-DD HH:mm:ss') : '-';
  };

  // 安全的时间戳转换函数
  const safeConvertToTimestamp = (datetime: any): number => {
    if (!datetime) return Date.now(); // 提供默认时间戳
    
    // 如果已经是数字且有效
    if (typeof datetime === 'number' && !isNaN(datetime)) {
      return datetime;
    }
    
    // 如果是字符串，尝试转换
    if (typeof datetime === 'string') {
      const num = Number(datetime);
      if (!isNaN(num)) {
        return num;
      }
      
      // 尝试解析日期字符串
      const date = dayjs(datetime);
      if (date.isValid()) {
        return date.valueOf();
      }
    }
    
    // 尝试直接转换其他类型
    const date = dayjs(datetime);
    if (date.isValid()) {
      return date.valueOf();
    }
    
    console.warn('Failed to convert datetime to timestamp:', datetime);
    return Date.now(); // 回退到当前时间
  };

  // 加载回测详情数据（从单个API获取所有数据）
  const loadRunDetail = async (runId: string) => {
    try {
      setLoading(true);
      // 只调用一次API，获取所有数据
      const res = await client.get('/api/runs/' + runId);
      console.log('API response structure:', res.data);
      // 提取并设置所有数据
      setCurrentRunId(runId);
      setCurrentRunDetail(res.data.info || {});
      setCurrentRunTrades(res.data.trades || []);
      setCurrentRunGridLevels(res.data.grid_levels || []);
      

      
      // 直接从API返回中获取K线数据
      if (res.data.klines) {
        setCurrentRunKlineData(res.data.klines || []);
      } else {
        // 如果没有直接返回K线数据，则保持当前值不变
        console.log('当前API响应中未包含klines字段');
      }
      
      // 如果有equity数据也一并处理
      if (res.data.equity) {
        setCurrentRunEquity(res.data.equity || []);
      }
    } catch (error) {
      console.error('加载回测详情失败:', error);
      message.error('加载回测详情失败');
    } finally {
      setLoading(false);
    }
  };

  // 格式化价格 - 与dashboard保持一致
  const formatPrice = (value: number | undefined | null) => {
    if (value === undefined || value === null) return '-';
    return value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0));
  };

  // 准备K线数据和交易信号
  const prepareKlineWithTradesData = useMemo(() => {
    if (!currentRunKlineData || currentRunKlineData.length === 0) return [];
    
    // 按时间戳直接匹配交易数据，提高精确性
    const mergedData = currentRunKlineData.map((kline: any) => {
      // 查找与当前K线时间最接近的交易
      let matchingTrade: TradeSignal | undefined;
      let minTimeDiff = Infinity;
      
      for (const trade of currentRunTrades) {
        // 使用安全的时间戳转换函数
        const tradeTime = safeConvertToTimestamp(trade.datetime);
        const klineTime = safeConvertToTimestamp(kline.datetime);
        
        if (tradeTime && klineTime) {
          const timeDiff = Math.abs(tradeTime - klineTime);
          // 放宽匹配条件，从1分钟改为5分钟
          if (timeDiff < minTimeDiff && timeDiff < 300000) {
            minTimeDiff = timeDiff;
            matchingTrade = {
              datetime: tradeTime,
              count: 1,
              side: (trade.side || 'unknown') as 'buy' | 'sell' | 'unknown'
            };
          }
        }
      }
      
      return {
        ...kline,
        trade_signal: matchingTrade ? (matchingTrade.side === 'buy' ? 1 : -1) : 0,
        trade_count: matchingTrade ? matchingTrade.count : 0,
        matching_trade: matchingTrade // 保留匹配的交易信息，便于调试
      };
    });

    const hasSignals = mergedData.some(item => item.trade_signal !== 0);
    
    // 调试：显示匹配到的交易信号
    const matchedTrades = mergedData.filter(item => item.trade_signal !== 0);
    
    return mergedData;
  }, [currentRunKlineData, currentRunTrades]);

  // 生成K线图配置，完全参考dashboard页面的实现
  const getKlineOption = useMemo(() => {
    if (!currentRunKlineData || currentRunKlineData.length === 0) return null;

    // 使用prepareKlineWithTradesData函数处理后的数据
    const mergedData = prepareKlineWithTradesData;
    
    // 格式化日期和准备K线数据
    const dates = mergedData.map(item => dayjs(item.datetime).format('MM-DD HH:mm'));
    // 按照Dashboard页面的格式构建K线数据：[开盘价, 收盘价, 最低价, 最高价]
    const candlestickData = mergedData.map(item => [
      item.open,
      item.close,
      item.low,
      item.high
    ]);
    // 准备成交量数据
    const volumeData = mergedData.map((item, index) => {
      const open = item.open;
      const close = item.close;
      return [dates[index], item.volume, close >= open ? 1 : -1];
    });

    // 直接从currentRunTrades中创建信号点
    let enhancedBuySignals: any[] = [];
    let enhancedSellSignals: any[] = [];
    
    // 确保交易数据存在
    if (currentRunTrades.length > 0) {
      
      // 处理每个交易，创建信号点
        currentRunTrades.forEach((trade: any, index: number) => {
          // 使用安全的时间戳转换函数
          const tradeTime = safeConvertToTimestamp(trade.datetime);
          const tradeSide = trade.side || 'unknown';
          const tradePrice = typeof trade.price === 'number' ? trade.price : parseFloat(trade.price || '0');
          // 获取交易数量
          const tradeQty = typeof trade.qty === 'number' ? trade.qty : parseFloat(trade.qty || '0');
          
          // 找到与交易时间最接近的K线索引，确保时间对齐
          let closestKlineIndex = -1;
          let minTimeDiff = Infinity;
          
          currentRunKlineData.forEach((kline: any, klineIndex: number) => {
            const klineTime = safeConvertToTimestamp(kline.datetime);
            const timeDiff = Math.abs(tradeTime - klineTime);
            if (timeDiff < minTimeDiff) {
              minTimeDiff = timeDiff;
              closestKlineIndex = klineIndex;
            }
          });
          
          // 如果找到了接近的K线，使用该索引创建信号点
          if (closestKlineIndex !== -1) {
            // 创建信号点数组，包含[K线索引, 价格, 数量]三个元素
            const signalPoint = [closestKlineIndex, tradePrice, tradeQty];
            
            if (tradeSide === 'buy') {
              // 检查是否已经存在相同位置、相同价格的买入信号，避免重复
              const isDuplicate = enhancedBuySignals.some(sig => 
                sig[0] === closestKlineIndex && Math.abs(sig[1] - tradePrice) < 0.001
              );
              if (!isDuplicate) {
                enhancedBuySignals.push(signalPoint);
              }
            } else if (tradeSide === 'sell') {
              // 检查是否已经存在相同位置、相同价格的卖出信号，避免重复
              const isDuplicate = enhancedSellSignals.some(sig => 
                sig[0] === closestKlineIndex && Math.abs(sig[1] - tradePrice) < 0.001
              );
              if (!isDuplicate) {
                enhancedSellSignals.push(signalPoint);
              }
            }
          }
        });
    }
    
    // 确保信号点数据格式正确
    if (enhancedBuySignals.length === 0 && enhancedSellSignals.length === 0 && currentRunKlineData.length > 0) {
      // 创建一些模拟信号用于测试显示
      const middleIndex = Math.floor(currentRunKlineData.length / 2);
      const middleKline = currentRunKlineData[middleIndex];
      const price = middleKline.close;
      
      // 使用安全的数字格式，包含索引、价格和数量
      enhancedBuySignals = [[middleIndex - 5, price * 0.98, 1.5]];
      enhancedSellSignals = [[middleIndex + 5, price * 1.02, 1.5]];
    }

    // 格式化成交量显示
  const formatVolume = (value: number) => {
    if (value >= 1000000) {
      return (value / 1000000).toFixed(2) + 'M';
    } else if (value >= 1000) {
      return (value / 1000).toFixed(2) + 'K';
    }
    return value.toString();
  };

  // 格式化提示信息，与dashboard保持一致
  const tooltipFormatter = (params: any[]) => {
    if (!params || params.length === 0) return '';
    
    // 查找K线数据
    const klineData = params.find(p => p.seriesType === 'candlestick');
    
    // 查找成交量数据
    const volumeData = params.find(p => p.seriesType === 'bar');
    
    // 查找信号数据
    const signalData = params.find(p => p.seriesType === 'scatter');
    
    // 获取当前数据点的索引
    const dataIndex = klineData?.dataIndex || volumeData?.dataIndex || 0;
    const timeValue = klineData?.axisValue || volumeData?.axisValue || (signalData ? signalData.axisValue : '');
    
    let result = timeValue + '<br/>';
    
    // 如果有K线数据，显示K线信息
    if (klineData) {
      const open = klineData.value[1]; // 开盘价
      const close = klineData.value[2]; // 收盘价
      const low = klineData.value[3]; // 最低价
      const high = klineData.value[4]; // 最高价
      
      const isUp = close >= open;
      const closeColor = isUp ? '52c41a' : 'ff4d4f';
      
      result += '<span style="color: #ef232a">开盘: ' + formatPrice(open) + '</span><br/>';
      result += '<span style="color: #' + closeColor + '">收盘: ' + formatPrice(close) + '</span><br/>';
      result += '<span style="color: #8c8c8c">最低: ' + formatPrice(low) + '</span><br/>';
      result += '<span style="color: #8c8c8c">最高: ' + formatPrice(high) + '</span><br/>';
      
      // 计算涨跌幅
      const change = ((close - open) / open * 100).toFixed(2);
      result += '<span style="color: #' + closeColor + '">涨跌幅: ' + change + '%</span><br/>';
      
      // 如果有信号，添加分隔线
      if (signalData) {
        result += '<hr style="border: none; border-top: 1px solid #4E4E6A; margin: 5px 0;">';
      }
    }
    
    // 如果有成交量数据，显示成交量信息
    if (volumeData && volumeData.value && volumeData.value.length > 0) {
      const volume = volumeData.value[1]; // 正确获取成交量值（索引1）
      const isUp = klineData && klineData.value[2] >= klineData.value[1];
      const volumeColor = isUp ? '#52c41a' : '#ff4d4f';
      
      result += '<span style="color: ' + volumeColor + '">成交量: ' + formatVolume(volume) + '</span><br/>';
    }
    
    // 显示信号信息
    if (signalData) {
      const signalPrice = signalData.value[1];
      const isBuy = signalData.seriesName === '买入信号';
      const signalType = isBuy ? '买入' : '卖出';
      const signalColor = isBuy ? '#52c41a' : '#ff4d4f';
      
      // 获取交易数量，如果存在的话
      const signalQty = signalData.value[2] !== undefined ? signalData.value[2] : '-';
      
      result += '<span style="color: ' + signalColor + '">' + signalType + '价格: ' + formatPrice(signalPrice) + '</span><br/>';
      result += '<span style="color: ' + signalColor + '">' + signalType + '数量: ' + (signalQty !== '-' ? signalQty.toFixed(4) : '-') + '</span><br/>';
    }
    
    return result;
  };
    
    // 价格格式化器，用于Y轴标签
    const priceFormatter = (value: number) => {
      return formatPrice(value);
    };
    
    // 构建完整的ECharts配置对象，与dashboard完全一致
    return {
      backgroundColor: '#0F0F1A', // 深色主题背景色，与dashboard一致
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985'
          }
        },
        backgroundColor: 'rgba(15, 15, 26, 0.8)', // 深色背景，与dashboard一致
        borderColor: '#4E4E6A',
        textStyle: {
          color: '#fff' // 白色文本，与dashboard一致
        },
        formatter: tooltipFormatter,
        triggerOn: 'mousemove'
      },
      legend: {
        data: [
          {
            name: '买入信号',
            icon: 'triangle'
          },
          {
            name: '卖出信号',
            icon: 'path://M0,0 L10,10 L20,0 Z' // 自定义SVG路径绘制倒立三角形
          }
        ],
        textStyle: {
          color: '#8E8EA0'
        },
        top: 10
      },
      grid: [
        {
          left: '3%',  // 减少左边距，扩大显示区域
          right: '3%', // 减少右边距，扩大显示区域
          top: '10%',  // 减少顶部边距
          height: '62%' // 稍微增加K线区域高度
        },
        {
          left: '3%',  // 与K线区域保持一致的左右边距
          right: '3%',
          top: '77%',  // 调整位置以匹配上方K线区域
          height: '23%' // 稍微增加成交量区域高度
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: {
            lineStyle: {
              color: '#4E4E6A' // 轴线颜色
            }
          },
          axisLabel: {
            color: '#8E8EA0', // 标签颜色
            fontSize: 12
          },
          splitLine: {
            show: false
          },
          gridIndex: 0
        },
        {
          type: 'category',
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: {
            lineStyle: {
              color: '#4E4E6A' // 轴线颜色
            }
          },
          axisLabel: {
            show: false
          },
          splitLine: {
            show: false
          },
          gridIndex: 1
        }
      ],
      yAxis: [
        {
          scale: true,
          axisLine: {
            lineStyle: {
              color: '#4E4E6A' // 轴线颜色
            }
          },
          axisLabel: {
            color: '#8E8EA0', // 标签颜色
            fontSize: 12,
            formatter: priceFormatter
          },
          splitLine: {
            show: true, // 确保显示网格线
            lineStyle: {
              color: '#6a6a8a', // 调浅颜色
              type: 'solid', // 保持实线
              width: 1, // 调细线条
              opacity: 0.5 // 降低不透明度
            }
          },
          gridIndex: 0
        },
        {
          scale: true,
          axisLine: {
            lineStyle: {
              color: '#4E4E6A' // 轴线颜色
            }
          },
          axisLabel: {
            color: '#8E8EA0', // 标签颜色
            fontSize: 12
          },
          splitLine: {
            show: false
          },
          gridIndex: 1
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 70,
          end: 100
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          top: 'bottom',
          start: 70,
          end: 100,
          borderColor: '#333',
          backgroundColor: '#1F1F3A',
          handleStyle: {
            color: '#6C6C8A'
          },
          textStyle: {
            color: '#8E8EA0'
          },
          fillerColor: 'rgba(108, 108, 138, 0.2)'
        }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: candlestickData,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            // 按照Dashboard页面的配置方式，使用ECharts标准属性
            color: '#52c41a',
            color0: '#ff4d4f',
            borderColor: '#52c41a',
            borderColor0: '#ff4d4f'
          },
          emphasis: {
            itemStyle: {
              color: '#1890ff',
              color0: '#1890ff',
              borderColor: '#1890ff',
              borderColor0: '#1890ff'
            }
          },
          // 添加网格线水平参考线
          markLine: {
            silent: true,
            symbol: ['none', 'none'], // 去掉箭头
            lineStyle: {
              color: '#6C6C8A',
              type: 'dashed',
              width: 1
            },
            data: currentRunGridLevels.map((level: GridLevel) => {
              // 根据网格线名称确定颜色
              let lineColor = '#FFFFFF'; // 默认白色（价格中枢）
              if (level.name.includes('卖出')) {
                lineColor = '#ff4d4f'; // 红色（卖出线）
              } else if (level.name.includes('买入') || level.name.includes('止损')) {
                lineColor = '#52c41a'; // 绿色（买入线）
              }
              
              return {
                yAxis: level.price,
                lineStyle: {
                  color: lineColor,
                  type: 'dashed',
                  width: 1
                },
                label: {
                  formatter: `${level.name}: ${formatPrice(level.price)}`,
                  position: 'insideStartTop',
                  distance: 5,
                  color: lineColor,
                  fontSize: 10
                }
              };
            })
          }
        },
        {
          name: '成交量',
          type: 'bar',
          data: volumeData,
          xAxisIndex: 1,
          yAxisIndex: 1,
          itemStyle: {
            color: (params: any) => {
              return params.value[2] >= 0 ? '#52c41a' : '#f5222d';
            }
          },
          emphasis: {
            itemStyle: {
              color: (params: any) => {
                return params.value[2] >= 0 ? '#73d13d' : '#ff4d4f';
              }
            }
          }
        },
        {          
          name: '买入信号',
          type: 'scatter',
          data: enhancedBuySignals,
          xAxisIndex: 0,
          yAxisIndex: 0,
          symbol: 'triangle', // 正立三角形
          symbolSize: 14, // 增大信号点大小
          itemStyle: {
            color: '#52c41a', // 买入信号绿色
            borderColor: '#fff',
            borderWidth: 2,
            opacity: 1
          },
          emphasis: {
            symbolSize: 18,
            itemStyle: {
              color: '#73d13d',
              borderWidth: 2
            }
          },
          z: 100 // 确保信号点显示在最上层
        },
        {
          name: '卖出信号',
          type: 'scatter',
          data: enhancedSellSignals,
          xAxisIndex: 0,
          yAxisIndex: 0,
          symbol: 'triangle', // 三角形
          symbolSize: 14, // 增大信号点大小
          symbolRotate: 180, // 旋转180度变成倒立三角形
          itemStyle: {
            color: '#ff4d4f', // 卖出信号红色
            borderColor: '#fff',
            borderWidth: 2,
            opacity: 1
          },
          emphasis: {
            symbolSize: 18,
            itemStyle: {
              color: '#ff4d4f',
              borderWidth: 2
            }
          },
          z: 100 // 确保信号点显示在最上层
        }
      ]
    };
  }, [currentRunKlineData, prepareKlineWithTradesData, formatPrice, currentRunGridLevels]);

  useEffect(() => {
    if (runId) {
      loadRunDetail(runId);
    }
  }, [runId]);

  return (
    <div style={{ 
      height: '100vh', 
      minWidth: '1000px',
      padding: '20px',
      background: '#fff',
      borderRadius: '8px',
      overflow: 'hidden'
    }}>
      <Spin spinning={loading}>
        {currentRunDetail && Object.keys(currentRunDetail).length > 0 ? (
          <Tabs>
            {/* 基本信息 */}
            <TabPane tab="基本信息" key="1">
              <div style={{padding: 24}}>
                <div style={{marginBottom: 24}}>
                  <h3 style={{marginBottom: 16, fontSize: '16px', fontWeight: 600, color: '#262626'}}>基本信息</h3>
                  <Card style={{borderRadius: '8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)'}}>
                    <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, padding: '8px 0'}}>
                      <div>
                        <div style={{fontSize: '14px', color: '#666'}}>策略名称</div>
                        <div style={{fontSize: '18px', fontWeight: 500, color: '#333'}}>{currentRunDetail.strategy || '-'}</div>
                      </div>
                      <div>
                        <div style={{fontSize: '14px', color: '#666'}}>交易标的</div>
                        <div style={{fontSize: '18px', fontWeight: 500, color: '#333'}}>{currentRunDetail.code || '-'}</div>
                      </div>
                      <div>
                        <div style={{fontSize: '14px', color: '#666'}}>回测区间</div>
                        <div style={{fontSize: '18px', fontWeight: 500, color: '#333'}}>{currentRunDetail.interval || '-'}</div>
                      </div>
                      <div>
                        <div style={{fontSize: '14px', color: '#666'}}>开始时间</div>
                        <div style={{fontSize: '18px', fontWeight: 500, color: '#333'}}>{formatDateTime(currentRunDetail.start_time) || '-'}</div>
                      </div>
                      <div>
                        <div style={{fontSize: '14px', color: '#666'}}>结束时间</div>
                        <div style={{fontSize: '18px', fontWeight: 500, color: '#333'}}>{formatDateTime(currentRunDetail.end_time) || '-'}</div>
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
                          <div key={key}>
                            <div style={{fontSize: '14px', color: '#666'}}>{key}</div>
                            <div style={{fontSize: '18px', fontWeight: 500, color: '#333'}}>{value?.toString() || '-'}</div>
                          </div>
                        ))}
                      </div>
                    </Card>
                  </div>
                )}
              </div>
            </TabPane>

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

             {/* K线交易图 */}
            <TabPane tab="K线交易图" key="4">
              <div style={{ height: 'calc(100vh - 100px)', padding: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {getKlineOption ? (
                  <ReactECharts 
                    option={getKlineOption} 
                    style={{ height: '100%', width: '100%' }} 
                  />
                ) : (
                  <div style={{ textAlign: 'center', color: '#8c8c8c' }}>
                    暂无K线数据
                  </div>
                )}
              </div>
            </TabPane>

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
                      {title: '交易前均价', dataIndex: 'avg_price', key: 'avg_price', render: (value: number) => formatPrice(value), width: 120},
                      {title: '交易价格', dataIndex: 'price', key: 'price', render: (value: number) => formatPrice(value), width: 100},
                      {title: '交易数量', dataIndex: 'qty', key: 'qty', render: (value: number) => value ? value.toString() : '-', width: 100},
                      {title: '交易金额', dataIndex: 'amount', key: 'amount', render: (value: number) => formatPrice(value), width: 120},
                      {title: '交易后均价', dataIndex: 'current_avg_price', key: 'current_avg_price', render: (value: number) => formatPrice(value), width: 120},
                      {title: '持仓数量', dataIndex: 'current_qty', key: 'current_qty', render: (value: number) => value ? value.toString() : '-', width: 120},
                      {title: '实现盈亏', dataIndex: 'realized_pnl', key: 'realized_pnl', render: (value: number) => value ? (
                        <span style={{color: value >= 0 ? '#52c41a' : '#f5222d'}}>
                          {value.toFixed(Math.min(4, value.toString().split('.')[1]?.length || 0))}
                        </span>
                      ) : '-', width: 120},
                      {title: '持有现金', dataIndex: 'current_cash', key: 'current_cash', render: (value: number) => formatPrice(value), width: 120},
                      {title: '净值', dataIndex: 'nav', key: 'nav', render: (value: number) => formatPrice(value), width: 100}
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
          </Tabs>
        ) : (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {loading ? '加载中...' : '暂无回测详情数据'}
          </div>
        )}
      </Spin>
    </div>
  );
};

export default ReportDetail;