import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { Button, Tag, Segmented, Progress, Table, message, Spin } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SyncOutlined, SettingOutlined, CloseOutlined, EyeOutlined, EyeInvisibleOutlined, LoadingOutlined } from '@ant-design/icons';
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

/**
 * 根据牛熊分数获取牛熊阶段
 * @param score 牛熊分数（-7到7）
 * @returns 牛熊阶段描述
 */
const getBullBearPhase = (score: number): string => {
  if (score >= 5) return '强牛市';
  if (score >= 3) return '牛市';
  if (score >= 1) return '偏牛市';
  if (score <= -5) return '强熊市';
  if (score <= -3) return '熊市';
  if (score <= -1) return '偏熊市';
  return '中性';
};

/**
 * 根据恐惧贪婪指数获取分类
 * @param index 恐惧贪婪指数（0-100）
 * @returns 分类描述
 */
const getFearGreedClassification = (index: number): string => {
  if (index >= 90) return '极度贪婪';
  if (index >= 80) return '贪婪';
  if (index >= 70) return '偏贪婪';
  if (index <= 10) return '极度恐惧';
  if (index <= 20) return '恐惧';
  if (index <= 30) return '偏恐惧';
  return '中性';
};

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
  const [togglingSymbols, setTogglingSymbols] = useState<Set<string>>(new Set()); // 正在切换watch状态的symbol集合
  
  // 性能优化：添加防抖和节流引用
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const vmrFetchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const preloadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // 性能优化：添加数据缓存
  const dashboardDataCache = useRef<{
    data: any;
    timestamp: number;
  } | null>(null);
  const vmrDataCache = useRef<Map<string, { data: { series: any[]; timeframe: string; symbols: string[]; total_count: number }; timestamp: number }>>(new Map());
  const CACHE_DURATION = 5 * 60 * 1000; // 5分钟缓存
  
  // 防止React严格模式下的重复调用
  const hasInitializedRef = useRef(false);



  const fetchDashboardData = useCallback(async (forceRefresh = false) => {
    // 性能优化：检查缓存
    const now = Date.now();
    if (!forceRefresh && dashboardDataCache.current && 
        now - dashboardDataCache.current.timestamp < CACHE_DURATION) {
      const cachedData = dashboardDataCache.current.data;
      setMarketMetrics({
        bullBearScore: cachedData.market_sentiment.bull_bear_score,
        bullBearPhase: getBullBearPhase(cachedData.market_sentiment.bull_bear_score),
        bullBearUpdatedAt: cachedData.market_sentiment.last_updated,
        fearGreedValue: cachedData.market_sentiment.fear_greed_index,
        fearGreedClassification: getFearGreedClassification(cachedData.market_sentiment.fear_greed_index),
        fearGreedUpdatedAt: cachedData.market_sentiment.last_updated,
      });
      
      const top5StrongCoins: EnhancedStrongWeakCoin[] = cachedData.strong_coins.slice(0, 5);
      const top5WeakCoins: EnhancedStrongWeakCoin[] = cachedData.weak_coins.slice(0, 5);
      
      setStrongCoins(top5StrongCoins || []);
      setWeakCoins(top5WeakCoins || []);
      
      const tableData: CoinAnalysisTableItem[] = cachedData.coin_analysis.map((coin: any) => ({
        ...coin,
        quoteVolume: coin.volume_24h,
        ve: coin.ve_value
      }));
      
      const limitedData = tableData.slice(0, 300);
      setCoinAnalysisFullData(limitedData || []);
      
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
      
      message.success('使用缓存数据加载完成！');
      return;
    }
    
    setRefreshing(true);
    setCoinsLoading(true);
    setCoinAnalysisLoading(true);
    
    // 用户体验优化：显示加载状态
    setMarketMetrics({
      bullBearScore: 0,
      bullBearPhase: 'Neutral',
      fearGreedValue: 0,
    });
    setStrongCoins([]);
    setWeakCoins([]);
    setCoinAnalysisFullData([]);
    setCoinAnalysisData([]);
    
    // 显示加载提示
    const loadingMessage = message.loading('正在加载Dashboard数据，可能需要较长时间...', 0);
    
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
      const tableData: CoinAnalysisTableItem[] = dashboardSummary.coin_analysis.map((coin: any) => ({
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
      
      // 性能优化：缓存数据
      dashboardDataCache.current = {
        data: dashboardSummary,
        timestamp: Date.now()
      };
      
      // 成功加载后显示成功消息
      message.success('Dashboard数据加载完成！');
      
    } catch (error) {
      console.error('Failed to fetch dashboard data', error);
      // 用户体验优化：显示错误状态
      setMarketMetrics({
        bullBearScore: 0,
        bullBearPhase: 'Neutral',
        fearGreedValue: 0,
      });
      setStrongCoins([]);
      setWeakCoins([]);
      setCoinAnalysisFullData([]);
      setCoinAnalysisData([]);
      
      if (error && typeof error === 'object' && 'code' in error && error.code === 'ECONNABORTED') {
        message.error('Dashboard数据加载超时，请稍后重试或联系管理员优化查询性能');
      } else {
        message.error('获取Dashboard数据失败');
      }
    } finally {
      setRefreshing(false);
      setCoinsLoading(false);
      setCoinAnalysisLoading(false);
      // 关闭加载提示
      loadingMessage();
    }
  }, []);

  const fetchVmrData = useCallback(async (timeframe: string, symbols?: string[]) => {
    setVmrLoading(true);
    try {
      // 性能优化：检查缓存
      const now = Date.now();
      const cacheKey = symbols ? `${timeframe}_${symbols.join(',')}` : timeframe;
      const cachedData = vmrDataCache.current.get(cacheKey);
      if (cachedData && now - cachedData.timestamp < CACHE_DURATION) {
        setVmrSeries(cachedData.data);
        setVmrLoading(false);
        message.success(`使用缓存数据加载VMR时间序列（${timeframe}）`);
        return;
      }
      
      // 用户体验优化：显示加载状态
      setVmrSeries({
        series: [],
        timeframe: timeframe,
        symbols: [],
        total_count: 0
      });
      
      // 根据是否传递symbols参数决定调用方式
      const response = await getVmrSeries(
        timeframe,
        symbols, // 传递symbols参数，或者undefined让后端动态获取
        100
      );
      setVmrSeries(response);
      
      // 性能优化：保存到缓存
      vmrDataCache.current.set(cacheKey, {
        data: response,
        timestamp: now
      });
    } catch (error) {
      console.error('Failed to fetch VMR time series', error);
      message.error('获取VMR时间序列失败');
      // 用户体验优化：显示错误状态
      setVmrSeries({
        series: [],
        timeframe: timeframe,
        symbols: [],
        total_count: 0
      });
    } finally {
      setVmrLoading(false);
    }
  }, [message]);

  // 预加载其他时间框架的VMR数据
  const preloadVmrData = useCallback(async () => {
    const timeframes = ['30m', '4h', '1d', '3d'];
    
    for (const timeframe of timeframes) {
      if (timeframe !== vmrTimeframe) {
        try {
          const response = await getVmrSeries(timeframe);
          // 直接缓存响应数据，因为VmrSeriesResponse没有success属性
          vmrDataCache.current.set(timeframe, {
            data: response,
            timestamp: Date.now()
          });
        } catch (error) {
          console.warn(`预加载VMR数据失败（${timeframe}）:`, error);
        }
      }
    }
  }, [vmrTimeframe]);

  useEffect(() => {
    // 防止React严格模式下的重复调用
    if (hasInitializedRef.current) {
      return;
    }
    hasInitializedRef.current = true;
    
    fetchDashboardData();
    fetchVmrData(vmrTimeframe);
    
    // 延迟预加载其他时间框架数据
    if (preloadTimeoutRef.current) {
      clearTimeout(preloadTimeoutRef.current);
    }
    preloadTimeoutRef.current = setTimeout(() => {
      preloadVmrData();
    }, 2000); // 2秒后开始预加载
    
    // 设置自动更新定时器，每5分钟刷新一次数据
    const autoRefreshInterval = setInterval(() => {
      console.log('自动刷新Dashboard数据...');
      fetchDashboardData(true); // 强制刷新，不使用缓存
      fetchVmrData(vmrTimeframe);
    }, 5 * 60 * 1000); // 5分钟
    
    // 组件卸载时清除定时器
    return () => {
      clearInterval(autoRefreshInterval);
    };
  }, []); // 空依赖数组，确保只在组件挂载时执行一次

  const handleVmrTimeframeChange = (value: string | number) => {
    // 性能优化：节流处理，避免频繁切换时间框架
    if (vmrFetchTimeoutRef.current) {
      clearTimeout(vmrFetchTimeoutRef.current);
    }
    
    vmrFetchTimeoutRef.current = setTimeout(() => {
      setVmrTimeframe(value as '30m' | '1h' | '4h' | '1d' | '3d');
    }, 200);
  };

  /**
   * 处理关闭VMR卡片
   * @param symbol 要关闭的币种符号
   */
  const handleCloseVmrCard = async (symbol: string) => {
    // 立即设置loading状态，让用户立即看到反馈
    setClosingSymbols(prev => new Set(prev).add(symbol));
    
    // 立即更新前端本地状态，提供即时反馈
    // 从VMR数据中移除该币种，提供即时视觉反馈
    setVmrSeries(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        series: prev.series.filter(item => item.symbol !== symbol),
        symbols: prev.symbols.filter(s => s !== symbol),
        total_count: prev.total_count - 1
      };
    });
    
    // 使用setTimeout确保UI立即更新，然后再执行API调用
    setTimeout(async () => {
      try {
        // 调用后端API，将symbol的watch状态设置为false
        // 使用binance作为默认交易所，因为VMR数据中只包含symbol信息
        await client.put(`/api/market/market_codes`, { watch: false }, {
          params: { exchange: 'binance', symbol }
        });
        
        message.success(`已移除 ${symbol} 的观察`);
        
        // 调用物化视图即时刷新API，确保后端数据同步
        try {
          await client.post(`/api/v1/dashboard/refresh-coin-watch`, null, {
            params: { 
              symbol, 
              watch_status: false 
            }
          });
        } catch (refreshError) {
          console.warn('物化视图即时刷新失败，将在下次定时刷新时同步:', refreshError);
        }
        
        // 重新加载VMR数据，刷新曲线图
        // 从当前显示的币种列表中排除刚刚关闭的币种，避免重新获取
        const currentSymbols = vmrSeries?.symbols?.filter(s => s !== symbol) || [];
        await fetchVmrData(vmrTimeframe, currentSymbols.length > 0 ? currentSymbols : undefined);
        
      } catch (error) {
        console.error('Failed to close VMR card:', error);
        message.error(`移除 ${symbol} 观察失败`);
        
        // 如果API调用失败，回滚前端状态
        // 重新加载VMR数据恢复原始状态
        await fetchVmrData(vmrTimeframe);
      } finally {
        // 从正在关闭的集合中移除，隐藏loading效果
        setClosingSymbols(prev => {
          const newSet = new Set(prev);
          newSet.delete(symbol);
          return newSet;
        });
      }
    }, 0);
  };

  /**
   * 处理watch/unwatch操作
   * @param symbol 币种符号
   * @param currentWatchStatus 当前watch状态
   */
  const handleWatchToggle = async (symbol: string, currentWatchStatus: boolean) => {
    // 立即设置loading状态，让用户立即看到反馈
    setTogglingSymbols(prev => new Set(prev).add(symbol));
    
    // 立即更新前端本地状态，提供即时反馈
    const newWatchStatus = !currentWatchStatus;
    
    // 更新币种分析表的本地watch状态
    setCoinAnalysisFullData(prevData => 
      prevData.map(item => 
        item.symbol === symbol ? { ...item, watch: newWatchStatus } : item
      )
    );
    
    // 更新当前显示的币种分析数据
    setCoinAnalysisData(prevData => 
      prevData.map(item => 
        item.symbol === symbol ? { ...item, watch: newWatchStatus } : item
      )
    );
    
    // 使用setTimeout确保UI立即更新，然后再执行API调用
    setTimeout(async () => {
      try {
        // 调用后端API，切换symbol的watch状态
        // 使用binance作为默认交易所
        await client.put(`/api/market/market_codes`, { watch: newWatchStatus }, {
          params: { exchange: 'binance', symbol }
        });
        
        message.success(`${symbol} ${newWatchStatus ? '已添加到观察列表' : '已从观察列表移除'}`);
        
        // 调用物化视图即时刷新API，确保后端数据同步
        try {
          await client.post(`/api/v1/dashboard/refresh-coin-watch`, null, {
            params: { 
              symbol, 
              watch_status: newWatchStatus 
            }
          });
        } catch (refreshError) {
          console.warn('物化视图即时刷新失败，将在下次定时刷新时同步:', refreshError);
        }
        
        // 根据watch状态变化决定如何更新VMR数据
        if (newWatchStatus) {
          // 如果设置为watch=true，重新获取所有watch=true的币种数据
          // 从当前币种分析数据中获取所有watch=true的币种
          const watchedSymbols = coinAnalysisFullData
            .filter(item => item.watch)
            .map(item => item.symbol);
          await fetchVmrData(vmrTimeframe, watchedSymbols.length > 0 ? watchedSymbols : undefined);
        } else {
          // 如果设置为watch=false，从现有VMR数据中移除该币种
          const currentSymbols = vmrSeries?.symbols?.filter(s => s !== symbol) || [];
          await fetchVmrData(vmrTimeframe, currentSymbols.length > 0 ? currentSymbols : undefined);
        }
        
      } catch (error) {
        console.error('Failed to toggle watch status:', error);
        message.error(`操作失败`);
        
        // 如果API调用失败，回滚前端状态
        setCoinAnalysisFullData(prevData => 
          prevData.map(item => 
            item.symbol === symbol ? { ...item, watch: currentWatchStatus } : item
          )
        );
        setCoinAnalysisData(prevData => 
          prevData.map(item => 
            item.symbol === symbol ? { ...item, watch: currentWatchStatus } : item
          )
        );
      } finally {
        // 从正在切换的集合中移除，隐藏loading效果
        setTogglingSymbols(prev => {
          const newSet = new Set(prev);
          newSet.delete(symbol);
          return newSet;
        });
      }
    }, 0);
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
      render: (value) => <span className={styles.tableValue}>{value ? value.toLocaleString() : '0'}</span>,
    },
    {
      title: '24h 成交量',
      dataIndex: 'volume_24h',
      key: 'volume_24h',
      render: (value) => <span className={styles.tableValue}>{value ? value.toLocaleString() : '0'}</span>,
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
    {
      title: 'watch',
      dataIndex: 'watch',
      key: 'watch',
      width: 80,
      render: (watch: boolean, record: CoinAnalysisTableItem) => (
        <Button
          type="text"
          size="small"
          icon={togglingSymbols.has(record.symbol) ? <LoadingOutlined /> : (watch ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
          onClick={() => handleWatchToggle(record.symbol, watch)}
          style={{ 
            color: togglingSymbols.has(record.symbol) ? '#8c8c8c' : (watch ? '#1890ff' : '#8c8c8c'),
            border: 'none',
            boxShadow: 'none',
            transition: 'all 0.3s ease'
          }}
          className="watch-button"
          title={togglingSymbols.has(record.symbol) ? '切换中...' : (watch ? '取消观察' : '添加观察')}
          disabled={togglingSymbols.has(record.symbol)}
        />
      ),
    },
  ], []);

  const vmrChartOption = useMemo(() => {
    // 性能优化：添加图表渲染节流
    if (!vmrSeries || vmrSeries.series.length === 0) {
      return {
        grid: { left: 50, right: 20, top: 50, bottom: 50 },
        xAxis: { type: 'category', data: [] },
        yAxis: { type: 'value' },
        series: [],
        animation: false, // 性能优化：禁用动画
      };
    }

    // 性能优化：简化时间轴处理逻辑
    // 使用第一个有数据的series的时间轴作为基准，避免复杂的去重排序
    const firstSeriesWithData = vmrSeries.series.find((item: any) => item.data && item.data.length > 0);
    if (!firstSeriesWithData) {
      return {
        grid: { left: 50, right: 20, top: 50, bottom: 50 },
        xAxis: { type: 'category', data: [] },
        yAxis: { type: 'value' },
        series: [],
        animation: false, // 性能优化：禁用动画
      };
    }

    // 性能优化：限制数据点数量，避免渲染过多数据
    const maxDataPoints = 100; // 最多显示100个数据点
    const baseTimePoints = firstSeriesWithData.data.slice(-maxDataPoints).map((point: any) => point.datetime);
    const xAxisData = baseTimePoints.map((datetime: string) =>
      dayjs(datetime).format(vmrTimeframe === '1d' || vmrTimeframe === '3d' ? 'MM-DD' : 'MM-DD HH:mm')
    );

    const legendData: string[] = [];
    const seriesData = vmrSeries.series.map((item: any, index: number) => {
      legendData.push(item.symbol);
      const color = VMR_COLOR_PALETTE[index % VMR_COLOR_PALETTE.length];
      
      // 性能优化：使用Map创建时间点到数据的快速映射，并限制数据量
      const points = item.data || [];
      const recentData = points.slice(-maxDataPoints);
      
      const pointMap = new Map();
      recentData.forEach((point: any) => {
        pointMap.set(point.datetime, point);
      });
      
      // 直接使用基准时间轴，避免复杂的对齐计算
      const alignedData = baseTimePoints.map((datetime: string) => {
        const point = pointMap.get(datetime);
        return point ? Number((point.vmr * 100).toFixed(4)) : null;
      });
      
      return {
        name: item.symbol,
        type: 'line',
        smooth: true,
        symbol: 'none',
        color: color,
        lineStyle: { width: 2, color },
        emphasis: { focus: 'series' },
        connectNulls: true,
        data: alignedData,
        // 性能优化：简化区域渐变效果
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${color}33` },
              { offset: 1, color: `${color}0A` },
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
          
          // 性能优化：简化tooltip格式化逻辑
          // 直接使用params中已有的数据，避免复杂的查找
          const lines = params
            .filter(item => item.data !== null && item.data !== undefined)
            .sort((a, b) => Number(b.data) - Number(a.data))
            .map((item) => {
              // 直接从params中获取数据，避免重复查找
              const vmrValue = Number(item.data).toFixed(4);
              const returnPct = item.dataIndex !== undefined && item.seriesIndex !== undefined 
                ? (vmrSeries.series[item.seriesIndex]?.data?.[item.dataIndex]?.return_pct || 0)
                : 0;
              
              return `<span style=\"display:inline-block;margin-right:8px;border-radius:4px;width:8px;height:8px;background:${
                item.color
              };\"></span>${item.seriesName}: <strong style=\"color:${item.color}\">${vmrValue}</strong> (${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%)`;
            })
            .filter(line => line !== '')
            .join('<br/>');
          return `<div style=\"margin-bottom:8px;font-weight:bold;\">${axisLabel}</div>${lines}`;
        },
      },
      legend: {
        type: 'scroll',
        top: 0,
        icon: 'circle',
        textStyle: { color: '#d7daff', fontSize: 10 },
        data: legendData,
      },
      xAxis: {
        type: 'category',
        data: xAxisData,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#2f3a60' } },
        axisLabel: { 
          color: '#8b92b4',
          interval: Math.max(1, Math.ceil(xAxisData.length / 8)),
          rotate: 45,
          fontSize: 10,
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#2f3a60' } },
        axisLabel: {
          color: '#8b92b4',
          formatter: (value: number) => value.toFixed(2),
          fontSize: 10,
        },
        splitLine: { lineStyle: { color: 'rgba(47,58,96,0.35)' } },
        name: 'VMR × 100',
        nameTextStyle: { color: '#8b92b4' },
      },
      series: seriesData,
      animation: false,
      animationDuration: 0,
      animationEasing: 'linear',
      animationDelayUpdate: 0,
    };
  }, [vmrSeries, vmrTimeframe]);



  const handleRefresh = () => {
    // 性能优化：防抖处理，避免频繁刷新
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
    }
    
    refreshTimeoutRef.current = setTimeout(() => {
      fetchDashboardData(true); // 强制刷新，不使用缓存
    }, 300);
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
    // 性能优化：防抖处理，避免频繁操作
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
    }
    
    refreshTimeoutRef.current = setTimeout(() => {
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

      // 性能优化：虚拟滚动 - 只加载当前页面的数据
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
    }, 100);
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
            <ReactECharts
              option={vmrChartOption}
              style={{ height: 360, width: '100%' }}
              opts={{ 
                renderer: 'canvas', // 性能优化：使用canvas渲染器
                devicePixelRatio: window.devicePixelRatio > 1 ? 1 : window.devicePixelRatio, // 性能优化：限制像素比
              }}
              notMerge={true} // 性能优化：不合并配置
              lazyUpdate={true} // 性能优化：延迟更新
            />
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
                    {closingSymbols.has(item.symbol) ? (
                      <LoadingOutlined className={styles.closeIcon} style={{ color: '#8c8c8c' }} />
                    ) : (
                      <CloseOutlined 
                        className={styles.closeIcon}
                        onClick={() => handleCloseVmrCard(item.symbol)}
                        title="移除观察"
                      />
                    )}
                  </div>
                  <div className={styles.vmrSummaryMetric}>
                    <span>VMR × 100</span>
                    <span>{latestVmrScaled.toFixed(4)}</span>
                  </div>
                  <div className={styles.vmrSummaryMetric}>
                    <span>24h涨跌幅</span>
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
