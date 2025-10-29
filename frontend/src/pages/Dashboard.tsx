import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Tag, Segmented, Progress, Table, message, Spin } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SyncOutlined, SettingOutlined, CloseOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import client from '../api/client';
import {
  getDashboardSummary,
  type EnhancedStrongWeakCoin,
  type CoinAnalysisItem,
  getVmrSeries,
  type VmrSeriesResponse,
} from '../api/dashboardOptimized';
import ReactECharts from 'echarts-for-react';
import styles from './Dashboard.module.css';

type TrendCoin = {
  symbol: string;
  pair: string;
  change24h: number;
  vmr: number;
  composite: number;
  spark: number[];
};



type CoinAnalysisTableItem = CoinAnalysisItem & {
  // 为了兼容现有代码，添加别名字段
  quoteVolume?: number; // 对应volume_24h，改为可选字段
  ve?: number; // 对应ve_value，改为可选字段
};



type MarketMetrics = {
  bullBearScore: number;
  bullBearPhase: string;
  bullBearUpdatedAt?: string;
  fearGreedValue: number;
  fearGreedClassification?: string;
  fearGreedUpdatedAt?: string;
};

const VMR_TIMEFRAME_OPTIONS = [
  { label: '30分钟', value: '30m' },
  { label: '1小时', value: '1h' },
  { label: '4小时', value: '4h' },
  { label: '1天', value: '1d' },
  { label: '3天', value: '3d' },
];

const VMR_COLOR_PALETTE = [
  '#34d399',
  '#facc15',
  '#60a5fa',
  '#f472b6',
  '#f97316',
  '#a855f7',
  '#22d3ee',
  '#fb7185',
  '#4ade80',
  '#c084fc',
];


const Sparkline: React.FC<{ data: number[]; color: string }> = ({ data, color }) => {
  const width = 120;
  const height = 40;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data
    .map((value, index) => {
      if (data.length === 1) {
        return `0,${height / 2}`;
      }
      const x = (index / (data.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg className={styles.sparkline} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
        points={points}
      />
    </svg>
  );
};

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
const formatTimestamp = (value?: string) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '--');

const Dashboard: React.FC = () => {
  const [marketMode, setMarketMode] = useState<'牛市' | '中性' | '熊市'>('中性');
  const [refreshing, setRefreshing] = useState(false);
  const [marketMetrics, setMarketMetrics] = useState<MarketMetrics>({
    bullBearScore: 0,
    bullBearPhase: 'Neutral',
    fearGreedValue: 0,
  });
  const [strongCoins, setStrongCoins] = useState<EnhancedStrongWeakCoin[]>([]);
  const [weakCoins, setWeakCoins] = useState<EnhancedStrongWeakCoin[]>([]);
  const [coinsLoading, setCoinsLoading] = useState(false);
  const [coinAnalysisData, setCoinAnalysisData] = useState<CoinAnalysisTableItem[]>([]);
  const [coinAnalysisFullData, setCoinAnalysisFullData] = useState<CoinAnalysisTableItem[]>([]);
  const [coinAnalysisLoading, setCoinAnalysisLoading] = useState(false);
  const [coinAnalysisPagination, setCoinAnalysisPagination] = useState({
    page: 1,
    page_size: 10,
    total_count: 0,
    total_pages: 0,
    has_previous: false,
    has_next: false
  });
  const [coinAnalysisSort, setCoinAnalysisSort] = useState<{
    field?: string;
    order?: 'ascend' | 'descend';
  }>({});
  const [vmrTimeframe, setVmrTimeframe] = useState<'30m' | '1h' | '4h' | '1d' | '3d'>('1h');
  const [vmrSeries, setVmrSeries] = useState<VmrSeriesResponse | null>(null);
  const [vmrLoading, setVmrLoading] = useState(false);
  const [closingSymbols, setClosingSymbols] = useState<Set<string>>(new Set()); // 正在关闭的symbol集合

  const fetchDashboardData = useCallback(async () => {
    setRefreshing(true);
    setCoinsLoading(true);
    setCoinAnalysisLoading(true);
    
    try {
      // 只调用汇总接口，避免冗余调用
      const dashboardSummary = await getDashboardSummary();
      
      // 设置市场情绪数据 - 使用汇总接口中的市场情绪数据
      setMarketMetrics({
        bullBearScore: dashboardSummary.market_sentiment.bull_bear_score,
        bullBearPhase: getBullBearPhase(dashboardSummary.market_sentiment.bull_bear_score),
        bullBearUpdatedAt: dashboardSummary.market_sentiment.last_updated,
        fearGreedValue: dashboardSummary.market_sentiment.fear_greed_index,
        fearGreedClassification: getFearGreedClassification(dashboardSummary.market_sentiment.fear_greed_index),
        fearGreedUpdatedAt: dashboardSummary.market_sentiment.last_updated,
      });
      
      // 使用汇总接口数据设置强势弱势币种数据
      const top5StrongCoins: EnhancedStrongWeakCoin[] = dashboardSummary.strong_coins.slice(0, 5);
      const top5WeakCoins: EnhancedStrongWeakCoin[] = dashboardSummary.weak_coins.slice(0, 5);
      
      setStrongCoins(top5StrongCoins || []);
      setWeakCoins(top5WeakCoins || []);
      
      // 设置币种分析表数据
      const tableData: CoinAnalysisTableItem[] = dashboardSummary.coin_analysis.map(coin => ({
        ...coin,
        quoteVolume: coin.volume_24h, // 映射volume_24h到quoteVolume
        ve: coin.ve_value // 映射ve_value到ve
      }));
      
      // 限制总记录数不超过300
      const limitedData = tableData.slice(0, 300);
      
      setCoinAnalysisFullData(limitedData || []);
      
      // 初始显示前10条数据
      const initialDisplayData = limitedData.slice(0, 10);
      setCoinAnalysisData(initialDisplayData || []);
      setCoinAnalysisPagination({
        page: 1,
        page_size: 10,
        total_count: limitedData.length,
        total_pages: Math.ceil(limitedData.length / 10),
        has_previous: false,
        has_next: limitedData.length > 10
      });
      
      // 不再需要设置vmrSelectedSymbols，后端会动态获取所有watch=true且quotecurrency=USDT的symbol
      
    } catch (error) {
      console.error('Failed to fetch dashboard data', error);
      message.error('获取Dashboard数据失败');
    } finally {
      setRefreshing(false);
      setCoinsLoading(false);
      setCoinAnalysisLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const fetchVmrData = useCallback(async (timeframe: string) => {
    setVmrLoading(true);
    try {
      // 不传递symbols参数，后端会动态获取watch=true且quotecurrency=USDT的symbol
      const response = await getVmrSeries(
        timeframe,
        undefined, // 不传递symbols参数，让后端动态获取
        100
      );
      setVmrSeries(response);
    } catch (error) {
      console.error('Failed to fetch VMR time series', error);
      message.error('获取VMR时间序列失败');
    } finally {
      setVmrLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchVmrData(vmrTimeframe);
  }, [vmrTimeframe, fetchVmrData]);

  const handleVmrTimeframeChange = (value: string | number) => {
    setVmrTimeframe(value as '30m' | '1h' | '4h' | '1d' | '3d');
  };

  /**
   * 处理关闭VMR卡片
   * @param symbol 要关闭的币种符号
   */
  const handleCloseVmrCard = async (symbol: string) => {
    // 添加到正在关闭的集合
    setClosingSymbols(prev => new Set(prev).add(symbol));
    
    try {
      // 调用后端API，将symbol的watch状态设置为false
      // 使用binance作为默认交易所，因为VMR数据中只包含symbol信息
      await client.put(`/api/market/market_codes/binance`, { watch: false }, {
        params: { symbol }
      });
      
      message.success(`已移除 ${symbol} 的观察`);
      
      // 重新加载VMR数据，刷新曲线图
      await fetchVmrData(vmrTimeframe);
      
    } catch (error) {
      console.error('Failed to close VMR card:', error);
      message.error(`移除 ${symbol} 观察失败`);
    } finally {
      // 从正在关闭的集合中移除
      setClosingSymbols(prev => {
        const newSet = new Set(prev);
        newSet.delete(symbol);
        return newSet;
      });
    }
  };

  const biasScore = marketMetrics.bullBearScore ?? 0;
  const clampedScore = clamp(biasScore, -7, 7);
  const gaugePercent = ((clampedScore + 7) / 14) * 100;
  const fearGreedValue = clamp(marketMetrics.fearGreedValue ?? 0, 0, 100);

  const columns: ColumnsType<CoinAnalysisTableItem> = useMemo(() => [
    {
      title: '币种',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (symbol) => (
        <div className={styles.coinCell}>
          <div className={styles.coinSymbol}>{symbol}</div>
          <div className={styles.coinPair}>{symbol}-USDT</div>
        </div>
      ),
    },
    {
      title: '市值',
      dataIndex: 'market_cap',
      key: 'market_cap',
      render: (value) => <span className={styles.tableValue}>{value.toLocaleString()}</span>,
    },
    {
      title: '24h 成交量',
      dataIndex: 'volume_24h',
      key: 'volume_24h',
      render: (value) => <span className={styles.tableValue}>{value.toLocaleString()}</span>,
    },
    {
      title: ({ sortOrder }) => {
        const arrow = sortOrder === 'ascend' ? '↑' : sortOrder === 'descend' ? '↓' : '↕';
        return `24h VMR ${arrow}`;
      },
      dataIndex: 'vmr',
      key: 'vmr',
      sorter: (a, b) => (a.vmr || 0) - (b.vmr || 0),
      sortDirections: ['descend', 'ascend'],
      render: (value) => <span className={styles.tableValue}>{value ? value.toFixed(6) : '0.000000'}</span>,
    },
    {
      title: ({ sortOrder }) => {
        const arrow = sortOrder === 'ascend' ? '↑' : sortOrder === 'descend' ? '↓' : '↕';
        return `VE ${arrow}`;
      },
      dataIndex: 've_value',
      key: 've_value',
      sorter: (a, b) => (a.ve_value || 0) - (b.ve_value || 0),
      sortDirections: ['descend', 'ascend'],
      render: (value) => <span className={styles.tableValue}>{value ? value.toFixed(6) : '0.000000'}</span>,
    },
    {
      title: ({ sortOrder }) => {
        const arrow = sortOrder === 'ascend' ? '↑' : sortOrder === 'descend' ? '↓' : '↕';
        return `复合分数 ${arrow}`;
      },
      dataIndex: 'composite_score',
      key: 'composite_score',
      sorter: (a, b) => (a.composite_score || 0) - (b.composite_score || 0),
      sortDirections: ['descend', 'ascend'],
      render: (value) => <span className={styles.tableValue}>{value ? value.toFixed(6) : '0.000000'}</span>,
    },
  ], []);

  const vmrChartOption = useMemo(() => {
    if (!vmrSeries || vmrSeries.series.length === 0) {
      return {
        grid: { left: 50, right: 20, top: 50, bottom: 50 },
        xAxis: { type: 'category', data: [] },
        yAxis: { type: 'value' },
        series: [],
      };
    }

    // 获取所有有数据的series，合并时间轴
    const allDataPoints = vmrSeries.series.flatMap((item: any) => item.data || []);
    
    // 去重并排序时间点
    const uniqueTimes = [...new Set(allDataPoints.map((point: any) => point.datetime))]
      .sort((a, b) => new Date(a).getTime() - new Date(b).getTime());
    
    const xAxisData = uniqueTimes.map((datetime: string) =>
      dayjs(datetime).format(vmrTimeframe === '1d' || vmrTimeframe === '3d' ? 'MM-DD' : 'MM-DD HH:mm')
    );

    const legendData: string[] = [];
    const seriesData = vmrSeries.series.map((item: any, index: number) => {
      legendData.push(item.symbol);
      const color = VMR_COLOR_PALETTE[index % VMR_COLOR_PALETTE.length];
      
      // 将后端返回的data字段映射为前端期望的points格式
      const points = item.data || [];
      
      // 创建时间点映射，便于数据对齐
      const pointMap = new Map(points.map((point: any) => [point.datetime, point]));
      
      // 将数据对齐到统一的时间轴上
      const alignedData = uniqueTimes.map((datetime: string) => {
        const point = pointMap.get(datetime) as any;
        return point ? Number((point.vmr * 100).toFixed(4)) : null; // 使用null表示缺失数据
      });
      
      return {
        name: item.symbol,
        type: 'line',
        smooth: true,
        symbol: 'none',
        color: color, // 添加color属性，确保tooltip和图例能正确获取颜色
        lineStyle: { width: 2, color },
        emphasis: { focus: 'series' },
        connectNulls: true, // 允许连接空值
        data: alignedData,
        // 添加区域渐变效果，增强视觉区分度
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${color}33` }, // 半透明
              { offset: 1, color: `${color}0A` }, // 更透明
            ],
          },
        },
      };
    });

    return {
      grid: { left: 50, right: 20, top: 50, bottom: 50 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15,16,28,0.92)',
        borderColor: '#2f3a60',
        textStyle: { color: '#f4f5fb' },
        formatter: (params: any[]) => {
          if (!params?.length || !vmrSeries?.series) return '';
          const axisLabel = params[0].axisValue;
          
          // 按VMR值排序，便于查看
          const sortedParams = [...params].sort((a, b) => Number(b.data) - Number(a.data));
          
          const lines = sortedParams
            .map((item) => {
              // 获取对应的原始数据点，包含return_pct信息
              const seriesIndex = vmrSeries.series.findIndex((s: any) => s.symbol === item.seriesName);
              if (seriesIndex === -1) return '';
              
              // 通过时间点匹配找到对应的原始数据
              const seriesData = vmrSeries.series[seriesIndex]?.data || [];
              
              // 直接通过时间戳匹配，避免作用域问题
              const originalData = seriesData.find((point: any) => {
                const pointTime = dayjs(point.datetime).format(vmrTimeframe === '1d' || vmrTimeframe === '3d' ? 'MM-DD' : 'MM-DD HH:mm');
                return pointTime === axisLabel;
              });
              
              if (!originalData) return '';
              
              const returnPct = originalData.return_pct || 0;
              
              return `<span style=\"display:inline-block;margin-right:8px;border-radius:4px;width:8px;height:8px;background:${
                item.color
              };\"></span>${item.seriesName}: <strong style=\"color:${item.color}\">${Number(item.data).toFixed(4)}</strong> (${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%)`;
            })
            .filter(line => line !== '') // 过滤掉空行
            .join('<br/>');
          return `<div style=\"margin-bottom:8px;font-weight:bold;\">${axisLabel}</div>${lines}`;
        },
      },
      legend: {
        type: 'scroll',
        top: 0,
        icon: 'circle',
        textStyle: { color: '#d7daff' },
        data: legendData,
      },
      xAxis: {
        type: 'category',
        data: xAxisData,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#2f3a60' } },
        axisLabel: { color: '#8b92b4' },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#2f3a60' } },
        axisLabel: {
          color: '#8b92b4',
          formatter: (value: number) => value.toFixed(2),
        },
        splitLine: { lineStyle: { color: 'rgba(47,58,96,0.35)' } },
        name: 'VMR × 100',
        nameTextStyle: { color: '#8b92b4' },
      },
      series: seriesData,
    };
  }, [vmrSeries, vmrTimeframe]);

  const vmrChangeLabel = useMemo(() => {
    // 根据时间框架确定变化标签
    switch (vmrTimeframe) {
      case '30m':
        return '30分钟';
      case '1h':
        return '1小时';
      case '4h':
        return '4小时';
      case '1d':
        return '1天';
      case '3d':
        return '3天';
      default:
        return '变化';
    }
  }, [vmrTimeframe]);

  // 根据牛熊市分数获取对应的阶段描述
  const getBullBearPhase = (score: number): string => {
    if (score >= 5) return 'Strong Bull';
    if (score >= 2) return 'Bull';
    if (score >= -2) return 'Neutral';
    if (score >= -5) return 'Bear';
    return 'Strong Bear';
  };

  // 根据恐惧贪婪指数获取对应的分类描述
  const getFearGreedClassification = (value: number): string => {
    if (value >= 80) return 'Extreme Greed';
    if (value >= 60) return 'Greed';
    if (value >= 40) return 'Neutral';
    if (value >= 20) return 'Fear';
    return 'Extreme Fear';
  };

  const handleRefresh = () => {
    fetchDashboardData();
  };

  // 处理币种分析表排序
  const handleCoinAnalysisTableSort = useCallback((field: string, order: 'ascend' | 'descend' | null) => {
    setCoinAnalysisSort({
      field: order ? field : undefined,
      order: order || undefined
    });
  }, []);

  // 处理币种分析表分页和排序
  const handleCoinAnalysisTableChange = useCallback((page: number, pageSize: number, sorter?: any) => {
    // 处理排序
    if (sorter) {
      const { field, order } = sorter;
      handleCoinAnalysisTableSort(field, order);
    }

    // 由于使用汇总接口，分页和排序在客户端处理
    let sortedData = [...coinAnalysisFullData];
    
    // 应用排序
    if (coinAnalysisSort.field && coinAnalysisSort.order) {
      sortedData.sort((a, b) => {
        const aValue = a[coinAnalysisSort.field as keyof CoinAnalysisTableItem] as number || 0;
        const bValue = b[coinAnalysisSort.field as keyof CoinAnalysisTableItem] as number || 0;
        
        if (coinAnalysisSort.order === 'ascend') {
          return aValue - bValue;
        } else {
          return bValue - aValue;
        }
      });
    }

    // 分页处理
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginatedData = sortedData.slice(startIndex, endIndex);
    
    setCoinAnalysisData(paginatedData);
    setCoinAnalysisPagination({
      page,
      page_size: pageSize,
      total_count: sortedData.length,
      total_pages: Math.ceil(sortedData.length / pageSize),
      has_previous: page > 1,
      has_next: page < Math.ceil(sortedData.length / pageSize)
    });
  }, [coinAnalysisFullData, coinAnalysisSort]);

  // 将API返回的EnhancedStrongWeakCoin数据转换为前端需要的TrendCoin格式
  // 修复convertToTrendCoin函数中的类型错误
  const convertToTrendCoin = (coin: EnhancedStrongWeakCoin): TrendCoin => {
    return {
      symbol: coin.symbol,
      pair: coin.symbol + '-USDT',
      change24h: coin.gain_24h || 0, // 处理undefined情况
      vmr: coin.vmr_total || 0, // 使用vmr_total字段作为VMR值（后端API返回vmr_total字段）
      composite: coin.composite_score || 0, // 使用composite_score字段作为复合分数
      spark: coin.hourly_data ? coin.hourly_data.map(item => item.close) : [coin.current_price || 0] // 使用小时数据作为sparkline
    };
  };

  const renderTrendList = (items: EnhancedStrongWeakCoin[], trend: 'bullish' | 'bearish') => {
    if (coinsLoading) {
      return (
        <div className={styles.loadingContainer}>
          <div className={styles.loadingText}>加载中...</div>
        </div>
      );
    }
    
    if (items.length === 0) {
      return (
        <div className={styles.emptyContainer}>
          <div className={styles.emptyText}>暂无数据</div>
        </div>
      );
    }
    
    return (
      <ul className={styles.trendList}>
        {items.map((coin) => {
          const trendCoin = convertToTrendCoin(coin);
          return (
            <li key={coin.symbol} className={styles.trendItem}>
              <div className={styles.trendSymbol}>
                <div className={styles.symbolCircle}>{coin.symbol.slice(0, 2)}</div>
                <div>
                  <div className={styles.symbolLabel}>{coin.symbol}</div>
                  <div className={styles.symbolPair}>{`${coin.symbol}-USDT`}</div>
                  {/* 将复合分数值显示在币名称下方 */}
                  <div className={styles.compositeScore}>
                    复合分数: {coin.composite_score ? coin.composite_score.toFixed(3) : '0.000'}
                  </div>
                </div>
              </div>
              <div>
                <Sparkline
                  data={trendCoin.spark}
                  color={trend === 'bullish' ? '#34d399' : '#f87171'}
                />
                <div className={styles.trendMeta}>
                  <span
                    className={
                      trend === 'bullish'
                        ? styles.positiveChange
                        : styles.negativeChange
                    }
                  >
                    {coin.gain_24h !== undefined && coin.gain_24h > 0 ? '+' : ''}
                    {coin.gain_24h !== undefined ? coin.gain_24h.toFixed(2) : '0.00'}%
                  </span>
                  <span className={styles.vmrLabel}>VMR</span>
                  <span className={styles.vmrValue}>{coin.vmr_total ? coin.vmr_total.toFixed(3) : '0.000'}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    );
  };

  return (
    <div className={styles.dashboardPage}>
      <div className={styles.pageHeader}>
        <div className={styles.marketMode}>
          <span>市场模式:</span>
          <Segmented
            className={styles.segmented}
            options={['牛市', '中性', '熊市']}
            value={marketMode}
            onChange={(value) => setMarketMode(value as '牛市' | '中性' | '熊市')}
          />
        </div>
        <div className={styles.actionGroup}>
          <Button icon={<SyncOutlined />} ghost type="primary" loading={refreshing} onClick={handleRefresh}>
            刷新数据
          </Button>
          <Button icon={<SettingOutlined />} className={styles.darkButton}>
            观察设置
          </Button>
        </div>
      </div>

      <section className={`${styles.sectionCard} ${styles.marketBiasSection}`}>
        <div className={styles.sectionHeader}>
          <div>
            <div className={styles.sectionTitle}>Market Bias Score</div>
            <div className={styles.sectionDescription}>实时市场情绪指标（computed: weight × features）</div>
          </div>
        </div>
        <div className={styles.gaugeRow}>
          <div className={styles.gaugeCard}>
            <Progress
              type="dashboard"
              percent={gaugePercent}
              gapDegree={60}
              strokeColor={{
                '0%': '#f5b642',
                '100%': '#657ce8',
              }}
              trailColor="#1c1d2d"
              format={() => (
                <span className={styles.scoreValue}>{clampedScore.toFixed(2)}</span>
              )}
            />
            <div className={styles.scoreScale}>
              <span className={styles.scaleLabel}>-7（熊市）</span>
              <span className={styles.scaleLabel}>0（中性）</span>
              <span className={styles.scaleLabel}>+7（牛市）</span>
            </div>
            <div className={styles.phaseInfo}>
              <span className={styles.phaseLabel}>{marketMetrics.bullBearPhase || 'Neutral'}</span>
              <span className={styles.phaseTime}>{formatTimestamp(marketMetrics.bullBearUpdatedAt)}</span>
            </div>
          </div>
          <div className={`${styles.statCard} ${styles.fearGreedCard}`}>
            <span className={styles.statLabel}>Fear &amp; Greed</span>
            <span className={styles.statValue} style={{ color: '#ff5d73' }}>
              {fearGreedValue.toFixed(0)}
            </span>
            <span className={styles.statSub}>{marketMetrics.fearGreedClassification || 'Index'}</span>
            <span className={styles.statMeta}>
              更新时间: {formatTimestamp(marketMetrics.fearGreedUpdatedAt)}
            </span>
          </div>
        </div>
      </section>

      <section className={styles.bottomGrid}>
        <div className={`${styles.sectionCard} ${styles.trendCard}`}>
          <div className={styles.trendHeader}>
            <div>
              <div className={styles.sectionTitle}>强势币种</div>
              <div className={styles.sectionDescription}>基于VMR总分数和24小时涨幅排序 · 显示前5名</div>
            </div>
            <Tag className={`${styles.trendTag} ${styles.bullishTag}`}>稳健</Tag>
          </div>
          {renderTrendList(strongCoins, 'bullish')}
        </div>

        <div className={`${styles.sectionCard} ${styles.tableCard}`}>
          <div className={styles.trendHeader}>
            <div>
              <div className={styles.sectionTitle}>币种分析表</div>
              <div className={styles.sectionDescription}>Top 300 币种 | 排除稳定币 | 市值 &gt; $100M | 支持VMR、VE、复合分数排序 | 分页显示</div>
            </div>
          </div>
          <div className={styles.tableWrapper}>
            <Table
              columns={columns}
              dataSource={coinAnalysisData.map(item => ({ ...item, key: item.symbol }))}
              pagination={{
                current: coinAnalysisPagination.page,
                pageSize: coinAnalysisPagination.page_size,
                total: coinAnalysisPagination.total_count,
                showSizeChanger: false,
                showQuickJumper: true,
                onChange: (page, pageSize) => {
                  handleCoinAnalysisTableChange(page, pageSize || coinAnalysisPagination.page_size);
                },
              }}
              onChange={(pagination, _filters, sorter) => {
                handleCoinAnalysisTableChange(
                  pagination.current || 1,
                  pagination.pageSize || coinAnalysisPagination.page_size,
                  sorter
                );
              }}
              loading={coinAnalysisLoading}
              size="small"
              rowClassName={() => styles.tableRow}
            />
          </div>
        </div>

        <div className={`${styles.sectionCard} ${styles.trendCard}`}>
          <div className={styles.trendHeader}>
            <div>
              <div className={styles.sectionTitle}>弱势币种</div>
              <div className={styles.sectionDescription}>基于VMR总分数和24小时涨幅排序 · 显示后5名（倒序）</div>
            </div>
            <Tag className={`${styles.trendTag} ${styles.bearishTag}`}>警戒</Tag>
          </div>
          {renderTrendList(weakCoins, 'bearish')}
        </div>
      </section>

      <section className={`${styles.sectionCard} ${styles.vmrSection}`}>
        <div className={styles.sectionHeader}>
          <div>
            <div className={styles.sectionTitle}>VMR 时间序列对比图</div>
            <div className={styles.sectionDescription}>动态显示所有watch=true且quotecurrency=USDT的币种 · 支持多时间框架横向趋势比较</div>
          </div>
          <div className={styles.vmrControls}>
            <Segmented
              options={VMR_TIMEFRAME_OPTIONS}
              value={vmrTimeframe}
              onChange={handleVmrTimeframeChange}
              className={styles.vmrSegmented}
            />
          </div>
        </div>

        <div className={styles.vmrChartWrapper}>
          {vmrLoading ? (
            <div className={styles.vmrChartLoading}>
              <Spin />
              <div style={{ marginTop: 16, color: '#8c8fa3' }}>加载VMR数据...</div>
            </div>
          ) : vmrSeries && vmrSeries.series.length ? (
            <ReactECharts option={vmrChartOption} style={{ height: 360, width: '100%' }} />
          ) : (
            <div className={styles.emptyContainer}>
              <div className={styles.emptyText}>暂无可用的VMR数据，请尝试选择其他币种</div>
            </div>
          )}
        </div>

        {vmrSeries && vmrSeries.series.length > 0 && (
          <div className={styles.vmrSummaryGrid}>
            {vmrSeries.series.map((item: any, index: number) => {
              // 使用与图表系列相同的颜色分配逻辑，确保颜色一致
              const color = VMR_COLOR_PALETTE[index % VMR_COLOR_PALETTE.length];
              
              // 计算当前VMR值和变化率（基于实际数据）
              const dataPoints = item.data || [];
              if (dataPoints.length === 0) {
                return null; // 跳过没有数据的币种
              }
              
              // 获取最新的VMR值并放大100倍，与图表显示保持一致
              const latestVmr = dataPoints[dataPoints.length - 1]?.vmr || 0;
              const latestVmrScaled = latestVmr * 100; // 放大100倍，与图表显示一致
              
              // 计算变化率（基于return_pct字段，这是正确的涨幅数据）
              const latestReturnPct = dataPoints[dataPoints.length - 1]?.return_pct || 0;
              const changeRate = latestReturnPct * 100; // return_pct已经是小数形式，乘以100转换为百分比
              const changePositive = changeRate >= 0;
              
              return (
                <div key={item.symbol} className={styles.vmrSummaryCard}>
                  <div className={styles.vmrSummaryHeader}>
                    <span className={styles.vmrBullet} style={{ backgroundColor: color }} />
                    <span>{item.symbol}</span>
                    <CloseOutlined 
                      className={styles.closeIcon}
                      onClick={() => handleCloseVmrCard(item.symbol)}
                    />
                  </div>
                  <div className={styles.vmrSummaryMetric}>
                    <span>VMR × 100</span>
                    <span>{latestVmrScaled.toFixed(4)}</span>
                </div>
                  <div className={styles.vmrSummaryMetric}>
                    <span>{vmrChangeLabel}</span>
                    <span className={changePositive ? styles.positiveChange : styles.negativeChange}>
                      {changePositive ? '+' : ''}
                      {changeRate.toFixed(2)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className={styles.vmrNotes}>
          <div>• 横向对比：观察同一时间框架下VMR随时间的变化趋势，VMR上升可能意味着资金逐步堆积。</div>
          <div>• 纵向对比：对比不同时间框架的VMR多维表现，寻找结构性强势币种。</div>
          <div>• 数据来源：实时指标数据（支持自动刷新）。切换时间窗或币种即可快速定位。</div>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
