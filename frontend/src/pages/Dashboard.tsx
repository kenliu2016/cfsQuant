import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Select, Button, Modal, Checkbox, message, DatePicker } from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import { ArrowUpOutlined, ArrowDownOutlined, SearchOutlined, BarChartOutlined, LineChartOutlined, CodeOutlined, CloseOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import client from '../api/client';
import { formatPriceWithUnit } from '../utils/priceFormatter';

// 定义回测结果类型
interface BacktestSignal {
  datetime: string;
  side: 'buy' | 'sell';
  price: number;
  qty: number;
}

// 定义网格级别类型
interface GridLevel {
  name: string;
  price: number;
}

// 定义策略回测状态类型
interface StrategyBacktestState {
  isRunning: boolean;
  signals: BacktestSignal[];
  hasResults: boolean;
  gridLevels?: GridLevel[]; // 网格级别数据（包含名称和价格）
}

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

// 格式化价格显示
const formatPrice = (value: number) => {
  return formatPriceWithUnit(value);
};

const Dashboard: React.FC = () => {
  // 市场概览数据
  const [marketOverview, setMarketOverview] = useState<any[]>([]);
  // 上次刷新时间
  const [lastUpdated, setLastUpdated] = useState<string>('');
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
  // 日期范围选择状态
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null]>([null, null]);
  const [showDatePicker, setShowDatePicker] = useState<boolean>(false);
  // 日历选择器是否有光标激活
  const [isDatePickerFocused, setIsDatePickerFocused] = useState<boolean>(false);
  // 定时器引用，用于5秒后自动收起日历选择器
  const datePickerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 存储从API获取的查询参数
  const [cachedQueryParams, setCachedQueryParams] = useState<any>(null);
  // 刷新按钮加载状态
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);


  // 策略相关状态
  const [showStrategiesModal, setShowStrategiesModal] = useState<boolean>(false);
  // 未使用的策略选择状态 - 保留结构
  // const [selectedStrategies, setSelectedStrategies] = useState<string[]>([]);
  const [floatingStrategies, setFloatingStrategies] = useState<Array<{id: string, name: string, position: {x: number, y: number}}>>([]);
  // API获取的策略数据 - 添加默认的硬编码策略数据
  const [strategiesData, setStrategiesData] = useState<Array<{id: string, name: string}>>([
    { id: '1', name: 'Hardcoded Strategy 1' },
    { id: '2', name: 'Hardcoded Strategy 2' },
    { id: '3', name: 'Hardcoded Strategy 3' }
  ]);
  // 策略加载状态 - 暂未使用但保留结构
  const [_, __] = useState<boolean>(false);
  
  // 回测相关状态
  const [strategyBacktestStates, setStrategyBacktestStates] = useState<Record<string, StrategyBacktestState>>({});
  
  // 从API获取策略数据
  const fetchStrategiesFromAPI = async () => {

    try {
      const response = await client.get('/api/strategies');
      // 假设后端返回的数据结构是 { rows: [{ id: string, name: string }] }
      const strategies = response.data.rows || response.data || [];
      setStrategiesData(strategies);
    } catch (error) {
      console.error('Failed to fetch strategies from API:', error);
      // API调用失败时使用空数组，避免显示mock数据
      setStrategiesData([]);
    }
  };

  // 监听showDatePicker和isDatePickerFocused状态变化，实现5秒自动收起日历选择器
  useEffect(() => {
    // 清除之前的定时器
    if (datePickerTimerRef.current) {
      clearTimeout(datePickerTimerRef.current);
    }

    // 当日历选择器显示且没有光标激活时，设置5秒后自动收起的定时器
    if (showDatePicker && !isDatePickerFocused) {
      datePickerTimerRef.current = setTimeout(() => {
        setShowDatePicker(false);
      }, 5000); // 5秒后自动收起
    }

    // 在组件卸载或重新渲染时清除定时器
    return () => {
      if (datePickerTimerRef.current) {
        clearTimeout(datePickerTimerRef.current);
      }
    };
  }, [showDatePicker, isDatePickerFocused]);

  // 运行策略回测
  const runBacktest = async (strategyId: string, strategyName: string) => {
    try {
      // 更新回测状态：设置当前策略为运行中，并清空所有其他策略的结果数据
      setStrategyBacktestStates(prev => {
        // 创建一个新的状态对象
        const newState: Record<string, StrategyBacktestState> = {};
        
        // 遍历所有策略ID
        Object.keys(prev).forEach(id => {
          if (id === strategyId) {
            // 当前要运行的策略：设置为运行中状态
            newState[id] = {
              isRunning: true,
              signals: [],
              gridLevels: [],
              hasResults: false
            };
          } else {
            // 其他策略：保留基本信息，但清空信号和网格级别数据
            newState[id] = {
              ...prev[id],
              signals: [],
              gridLevels: [],
              hasResults: false
            };
          }
        });
        
        // 如果这是一个新策略（之前不存在），也设置为运行中状态
        if (!prev[strategyId]) {
          newState[strategyId] = {
            isRunning: true,
            signals: [],
            gridLevels: [],
            hasResults: false
          };
        }
        
        return newState;
      });

      // 严格检查必要的参数
      if (!symbol) {
        throw new Error('未选择股票代码');
      }
      
      if (!strategyName || !strategyId) {
        throw new Error('未选择有效的策略');
      }
      
      if (!candleData || candleData.length === 0) {
        throw new Error('没有可用的K线数据');
      }
      
      // 准备调用后端run_backtest函数的参数
      const backtestParams = cachedQueryParams || {
        code: symbol,
        interval: timeframe,
        start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        end: new Date().toISOString()
      };
      
      const response = await client.post('/api/backtest', {
        params: backtestParams,
        strategy: strategyName
      });
      
      console.log('Backtest response:', response.data);
      // 处理回测结果
      const signals: BacktestSignal[] = response.data.signals || [];
      const gridLevels: GridLevel[] = response.data.grid_levels || [];
      
      // 更新回测状态为完成
      setStrategyBacktestStates(prev => ({
        ...prev,
        [strategyId]: {
          isRunning: false,
          signals: signals,
          hasResults: signals.length > 0,
          gridLevels: gridLevels
        }
      }));

      message.success(`策略 ${strategyName} 回测完成，生成 ${signals.length} 个信号`);
    } catch (error) {
      console.error(`Strategy ${strategyId} backtest failed:`, error);
      // 更新回测状态为失败
      setStrategyBacktestStates(prev => ({
        ...prev,
        [strategyId]: {
          isRunning: false,
          signals: [],
          gridLevels: [],
          hasResults: false
        }
      }));
      message.error(`策略回测失败: ${error instanceof Error ? error.message : '未知错误'}`);
    }
  };

  // 处理添加策略并自动运行回测
  const handleAddStrategy = async (strategyId: string, strategyName: string) => {
    // 检查是否已存在同名策略
    const existingIndex = floatingStrategies.findIndex(s => s.name === strategyName);
    
    if (existingIndex >= 0) {
      // 存在同名策略，覆盖它
      const updatedStrategies = [...floatingStrategies];
      updatedStrategies[existingIndex] = {
        id: strategyId,
        name: strategyName,
        position: updatedStrategies[existingIndex].position // 保留原位置
      };
      setFloatingStrategies(updatedStrategies);
    } else {
      // 不存在同名策略，添加新策略
      const newStrategy = {
        id: strategyId,
        name: strategyName,
        position: {
          x: 10 + floatingStrategies.length * 150, // 水平位置错开
          y: 0 // 垂直位置在这个布局中不那么重要了
        }
      };
      setFloatingStrategies([...floatingStrategies, newStrategy]);
    }
    
    // 无论是否选择股票，都先设置初始状态
    setStrategyBacktestStates(prev => ({
      ...prev,
      [strategyId]: {
        isRunning: false,
        signals: [],
        hasResults: false,
        gridLevels: []
      }
    }));
    
    // 如果选择了股票，则自动运行回测
    if (symbol) {
      await runBacktest(strategyId, strategyName);
    } else {
      message.warning('请先选择股票再添加策略');
    }
  };
  
  // 在组件挂载时就加载策略数据
  useEffect(() => {
    fetchStrategiesFromAPI();
  }, []);

  // 在打开策略对话框时加载策略数据
  useEffect(() => {
    if (showStrategiesModal) {
      fetchStrategiesFromAPI();
    }
  }, [showStrategiesModal]);

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



  
  // 优化：并行处理市场概览和K线数据请求
  useEffect(() => {
    if (symbols.length > 0 && symbol) {
      // 创建一个内存缓存键
      const cacheKey = `${symbol}_${timeframe}`;
      const lastRequestTime = sessionStorage.getItem(`lastRequest_${cacheKey}`);
      const now = Date.now();
      
      // 如果距离上次请求不足500毫秒，不重复请求（防止快速切换导致的频繁请求）
      if (lastRequestTime && now - parseInt(lastRequestTime) < 500) {
        return;
      }
      
      sessionStorage.setItem(`lastRequest_${cacheKey}`, now.toString());
      
      // 并行发起两个请求
      Promise.all([
        loadMarketOverview(symbols),
        fetchData()
      ]).catch(error => {
        console.error('数据加载失败:', error);
      });
    } else if (symbols.length > 0) {
      // 只有股票列表但没有选中股票时，只加载市场概览
      loadMarketOverview(symbols);
    }
  }, [timeframe, symbol, symbols]);

  // 当市场概览数据或选中的symbol变化时，更新选中股票的概览数据
  useEffect(() => {
    if (marketOverview.length > 0 && symbol) {
      const symbolInfo = marketOverview.find(item => item.code === symbol);
      if (symbolInfo) {
        setSelectedSymbolData(symbolInfo);
      }
    }
  }, [marketOverview, symbol]);

  // 调用API获取市场概览数据 - 使用批量查询优化性能并添加内存缓存
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
      
      // 创建缓存键
      const cacheKey = `market_overview_${codes}_${timeframe}`;
      
      // 尝试从内存缓存获取数据
      const cachedData = sessionStorage.getItem(cacheKey);
      if (cachedData) {
        const parsedData = JSON.parse(cachedData);
        // 检查缓存是否在5秒内有效
        if (Date.now() - parsedData.timestamp < 5000) {
          setMarketOverview(parsedData.data);
          const lastUpdatedNow = new Date();
          setLastUpdated(lastUpdatedNow.toLocaleTimeString());
          return parsedData.data; // 返回缓存数据以支持Promise.all
        }
      }
      
      // 根据不同的时间周期设置对应的limit参数
      const timeframeToLimit = {
        '1m': 2,
        '5m': 15,
        '15m': 45,
        '30m': 90,
        '60m': 180,
        '1h': 180,
        '4h': 720,
        '1D': 2,
        '1W': 21,
        '1M': 92
      };
      
      // 获取当前时间周期对应的limit值，如果没有匹配则默认使用2
      const limit = timeframeToLimit[timeframe as keyof typeof timeframeToLimit] || 2;
      
      // 生成精确到分钟的时间戳
      const timestampNow = new Date();
      // 格式化为YYYY-MM-DDTHH:mm（精确到分钟）
      const timestamp = `${timestampNow.getFullYear()}-${String(timestampNow.getMonth() + 1).padStart(2, '0')}-${String(timestampNow.getDate()).padStart(2, '0')}T${String(timestampNow.getHours()).padStart(2, '0')}:${String(timestampNow.getMinutes()).padStart(2, '0')}`;
      
      // 调用批量查询API
      const response = await client.get('/api/market/batch-candles', {
        params: {
          codes: codes,
          interval: timeframe,
          limit: limit,
          timestamp: timestamp
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
            const sortedData = [...dataArray].sort((a, b) => {
              // 确保datetime有效
              const timeA = a.datetime ? new Date(a.datetime).getTime() : 0;
              const timeB = b.datetime ? new Date(b.datetime).getTime() : 0;
              return timeB - timeA;
            }).filter(bar => bar.close !== undefined); // 过滤掉无效数据
            
            if (sortedData.length >= 2) {
              const latestBar = sortedData[0];
              const previousBar = sortedData[1];
              
              const isUp = latestBar.close >= previousBar.close;
              const change = (latestBar.close - previousBar.close).toFixed(4);
              const changePercent = ((latestBar.close - previousBar.close) / previousBar.close * 100).toFixed(2);
              
              return {
                id: item.code,
                code: item.code,
                name: item.name,
                price: parseFloat(latestBar.close.toFixed(4)), // 保持数值类型并控制精度
                change: parseFloat(change),
                changePercent: parseFloat(changePercent),
                trend: isUp ? 'up' : 'down'
              };
            } else if (sortedData.length === 1) {
              // 如果排序后只有一个有效数据，使用开盘价和收盘价计算变化
              const latestBar = sortedData[0];
              const isUp = latestBar.close >= latestBar.open;
              const change = (latestBar.close - latestBar.open).toFixed(4);
              const changePercent = ((latestBar.close - latestBar.open) / latestBar.open * 100).toFixed(2);
              
              return {
                id: item.code,
                code: item.code,
                name: item.name,
                price: parseFloat(latestBar.close.toFixed(4)), // 保持数值类型并控制精度
                change: parseFloat(change),
                changePercent: parseFloat(changePercent),
                trend: isUp ? 'up' : 'down'
              };
            }
          } else if (dataArray.length === 1) {
            // 只有一个bar的数据，使用开盘价和收盘价计算变化
            const latestBar = dataArray[0];
            const isUp = latestBar.close >= latestBar.open;
            const change = (latestBar.close - latestBar.open).toFixed(4);
            const changePercent = ((latestBar.close - latestBar.open) / latestBar.open * 100).toFixed(2);
            
            return {
              id: item.code,
              code: item.code,
              name: item.name,
              price: parseFloat(latestBar.close.toFixed(4)), // 保持数值类型并控制精度
              change: parseFloat(change),
              changePercent: parseFloat(changePercent),
              trend: isUp ? 'up' : 'down'
            };
          }
        }
        
        // 如果没有数据或数据无效，返回基本信息
        return {
          id: item.code,
          code: item.code,
          name: item.name,
          price: '-',
          change: 0,
          changePercent: 0,
          trend: 'neutral'
        };
      });
      

      setMarketOverview(marketOverviewData);
      // 更新最后刷新时间
      const lastUpdatedNow = new Date();
      setLastUpdated(lastUpdatedNow.toLocaleTimeString());
      
      // 保存到内存缓存
      sessionStorage.setItem(cacheKey, JSON.stringify({
        data: marketOverviewData,
        timestamp: Date.now()
      }));
      
      return marketOverviewData; // 返回数据以支持Promise.all
    } catch (error) {
      // 移除error logging以减少控制台输出
      // 直接返回空数据集，不进行降级处理
      setMarketOverview([]);
      // 更新最后刷新时间
      const now = new Date();
      setLastUpdated(now.toLocaleTimeString());
      return []; // 返回空数组以支持Promise.all
    }
  };

  // 已移除时间范围选择相关函数

  // 获取蜡烛图数据 - 添加内存缓存优化
  const fetchData = async (startTime?: Date, endTime?: Date): Promise<any[]> => {
    if (!symbol) return [];
    
    setIsLoading(true);
    try {
      const params: any = {
        code: symbol,
        interval: timeframe
      };
      
      // 如果提供了开始和结束时间，则添加到参数中
      if (startTime && endTime) {
        params.start = startTime.toISOString();
        params.end = endTime.toISOString();
      }
      
      // 创建缓存键
      const cacheKey = `candle_data_${symbol}_${timeframe}_${startTime ? startTime.getTime() : '0'}_${endTime ? endTime.getTime() : '0'}`;
      
      // 尝试从内存缓存获取数据
      const cachedData = sessionStorage.getItem(cacheKey);
      if (cachedData) {
        const parsedData = JSON.parse(cachedData);
        // 检查缓存是否在3秒内有效（K线数据更新频率更高，缓存时间较短）
        if (Date.now() - parsedData.timestamp < 3000) {
          if (parsedData.query_params) {
            setCachedQueryParams(parsedData.query_params);
          }
          setCandleData(parsedData.rows);
          setIsLoading(false);
          return parsedData.rows; // 返回缓存数据以支持Promise.all
        }
      }
      
      const response = await client.get('/api/market/candles', { params });
      // 暂存query_params
      if (response && response.data && response.data.query_params) {
        setCachedQueryParams(response.data.query_params);
      }
      if (response && response.data && response.data.rows) {
        const processedData = response.data.rows.map((item: any) => ({
          ...item,
          isUp: item.close >= item.open
        }));
        setCandleData(processedData);
        
        // 保存到内存缓存
        sessionStorage.setItem(cacheKey, JSON.stringify({
          query_params: response.data.query_params,
          rows: processedData,
          timestamp: Date.now()
        }));
        
        return processedData; // 返回数据以支持Promise.all
      }
      return [];
    } catch (error) {
      console.error('获取K线数据失败:', error);
      return [];
    } finally {
      setIsLoading(false);
    }
  };

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
  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const day = date.getDate().toString().padStart(2, '0');
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
});

    const candlestickData = candleData.map(item => [
  item.open,
  item.close,
  item.low,
  item.high
]);

    const lineData = candleData.map(item => item.close);

    // 准备回测信号数据
    const allSignals: any[] = [];
    const signalTypes = ['buy', 'sell'] as const;
    
    // 遍历所有策略的回测结果
    Object.entries(strategyBacktestStates).forEach(([strategyId, state]) => {
      if (state.hasResults && state.signals.length > 0) {
        // 为每种信号类型创建一个series
        signalTypes.forEach(type => {
          const signalsOfType = state.signals.filter((signal: BacktestSignal) => signal.side === type);
          if (signalsOfType.length > 0) {
            // 查找信号对应的K线数据点索引
              const dataPoints = signalsOfType.map((signal: BacktestSignal) => {
                const signalDate = new Date(signal.datetime).getTime();
                // 找到最接近的K线数据点
                let closestIndex = -1;
                let minTimeDiff = Infinity;
                
                // 遍历所有K线数据点，找到时间差最小的那个
                for (let i = 0; i < candleData.length; i++) {
                  const candleDate = new Date(candleData[i].datetime).getTime();
                  const timeDiff = Math.abs(candleDate - signalDate);
                  
                  // 扩大时间窗口到5分钟，提高匹配成功率
                  if (timeDiff < 5 * 60 * 1000 && timeDiff < minTimeDiff) {
                    minTimeDiff = timeDiff;
                    closestIndex = i;
                  }
                }
                
                if (closestIndex !== -1) {
                  return [closestIndex, signal.price];
                }
                return null;
            }).filter(Boolean) as [number, number][];
            
            if (dataPoints.length > 0) {
              // 根据信号类型设置不同的样式
              let color = '#fff';
              let symbolSize = 8;
              
              switch (type) {
                case 'buy':
                  // 向上绿色箭头代表买入
                  color = '#52c41a'; // 绿色
                  symbolSize = 12;
                  break;
                case 'sell':
                  // 向下红色箭头代表卖出
                  color = '#ff4d4f'; // 红色
                  symbolSize = 12;
                  break;
              }
              
              allSignals.push({
                name: `${strategyId}_${type}`,
                type: 'scatter',
                data: dataPoints,
                xAxisIndex: 0,
                yAxisIndex: 0,
                // 使用自定义symbol函数根据信号方向返回不同的图标
                symbol: (_value: any) => {
                  // 对于买入信号使用三角形
                  if (type === 'buy') {
                    return 'triangle';
                  }
                  // 对于卖出信号使用SVG路径定义真正的倒三角形
                  return 'path://M0,10 L10,0 L-10,0 Z';
                },
                symbolSize: symbolSize,
                // 设置偏移量使图标与K线有一定距离
                symbolOffset: type === 'buy' ? [0, symbolSize*1.5] : [0, -symbolSize*1.5],
                itemStyle: {
                  color: color,
                  borderWidth: 1,
                  borderColor: '#fff'
                },
                emphasis: {
                  itemStyle: {
                    shadowBlur: 4,
                    shadowColor: 'rgba(0, 0, 0, 0.3)'
                  }
                }
              });
            }
          }
        });
      }
    });

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
        formatter: function(params: any[]) {
  if (!params || params.length === 0) return '';
  
  // 查找K线数据
  let klineData = params.find(param => param.seriesName === 'K线图' || param.seriesName === '折线图');
  
  // 查找成交量数据
  const volumeData = params.find(param => param.seriesName === '成交量');
  
  // 查找信号数据
  const signalParams = params.filter(param => param.seriesName.includes('_buy') || param.seriesName.includes('_sell'));
  
  // 获取当前数据点的索引
  const dataIndex = klineData?.dataIndex || volumeData?.dataIndex || 0;
  const timeValue = klineData?.axisValue || volumeData?.axisValue || (signalParams.length > 0 ? signalParams[0].axisValue : '');
  
  let result = timeValue + '<br/>';
  
  // 如果有K线数据，显示K线信息
  if (klineData && candleData && candleData[dataIndex]) {
      const candle = candleData[dataIndex];
      result += '<span style="color: #ef232a">开盘: ' + candle.open + '</span><br/>';
      const closeColor = candle.close >= candle.open ? '52c41a' : 'ff4d4f';
      result += '<span style="color: #' + closeColor + '">收盘: ' + candle.close + '</span><br/>';
      result += '<span style="color: #8c8c8c">最低: ' + candle.low + '</span><br/>';
      result += '<span style="color: #8c8c8c">最高: ' + candle.high + '</span><br/>';
      
      // 计算涨跌幅
      const change = ((candle.close - candle.open) / candle.open * 100).toFixed(2);
      const changeColor = candle.close >= candle.open ? '52c41a' : 'ff4d4f';
      result += '<span style="color: #' + changeColor + '">涨跌幅: ' + change + '%</span><br/>';
      
      // 如果有信号，添加分隔线
      if (signalParams.length > 0) {
        result += '<hr style="border: none; border-top: 1px solid #4E4E6A; margin: 5px 0;">';
      }
  }
  
  // 如果有成交量数据，显示成交量信息
  if (volumeData && candleData && candleData[dataIndex] && candleData[dataIndex].volume) {
    const volume = candleData[dataIndex].volume;
    const volumeColor = candleData[dataIndex] && candleData[dataIndex].isUp !== undefined ? 
                       (candleData[dataIndex].isUp ? '#52c41a' : '#ff4d4f') : '#8c8c8c';
    result += '<span style="color: ' + volumeColor + '">成交量: ' + formatVolume(volume) + '</span><br/>';
  }
  
  // 显示信号信息
   if (signalParams.length > 0) {
     // 去重相同位置的信号
     const uniqueSignals: any[] = [];
     const signalKeys = new Set<string>();
     
     signalParams.forEach(param => {
       const signalKey = `${param.data[0]}-${param.data[1]}`;
       if (!signalKeys.has(signalKey)) {
         signalKeys.add(signalKey);
         uniqueSignals.push(param);
       }
     });
     
     uniqueSignals.forEach(param => {
      const signalIndex = param.data[0];
      const signalPrice = param.data[1];
      const isBuy = param.seriesName.includes('_buy');
      const signalType = isBuy ? '买入' : '卖出';
      const signalColor = isBuy ? '#52c41a' : '#ff4d4f';
      
      result += '<span style="color: ' + signalColor + '">' + signalType + '价格: ' + formatPrice(signalPrice) + '</span><br/>';
      
      // 尝试查找对应的信号对象获取更多信息
      for (const [_strategyId, state] of Object.entries(strategyBacktestStates)) {
        if (state.hasResults && state.signals) {
          const signalObj = state.signals.find((s: BacktestSignal) => {
            const signalDate = new Date(s.datetime).getTime();
            const candleDate = new Date(candleData[signalIndex]?.datetime).getTime();
            return Math.abs(candleDate - signalDate) < 5 * 60 * 1000 && 
                   Math.abs(s.price - signalPrice) < 0.0001 && 
                   s.side === (isBuy ? 'buy' : 'sell');
          });
          
          if (signalObj && signalObj.qty) {
            result += '<span style="color: ' + signalColor + '">' + signalType + '数量: ' + signalObj.qty + '</span><br/>';
            break;
          }
        }
      }
    });
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
        },
        // 买卖信号标记
        ...allSignals,
        // 网格线标记
        {
          name: '网格线',
          type: 'line',
          data: [], // 空数据，只显示markLine
          xAxisIndex: 0,
          yAxisIndex: 0,
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
            data: (() => {
              // 收集所有策略的网格线数据
              const gridLines: any[] = [];
              Object.entries(strategyBacktestStates).forEach(([_strategyId, state]) => {
                if (state.hasResults && state.gridLevels && state.gridLevels.length > 0) {
                  // 遍历网格线数据
                  state.gridLevels.forEach((level: GridLevel) => {
                    // 根据网格线名称确定颜色
                    let lineColor = '#FFFFFF'; // 默认白色（价格中枢）
                    if (level.name.includes('卖出')) {
                      lineColor = '#ff4d4f'; // 红色（卖出线）
                    } else if (level.name.includes('买入') || level.name.includes('止损')) {
                      lineColor = '#52c41a'; // 绿色（买入线）
                    }
                    
                    // 添加水平线配置
                    gridLines.push({
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
                    });
                  });
                }
              });
              return gridLines;
            })()
          }
        }
      ]
    };

    return option;
  }, [candleData, chartType, timeframe, formatPrice, strategyBacktestStates]);

  // 打开策略选择对话框

  // 关闭策略选择对话框 - 直接在Modal组件中使用setShowStrategiesModal
  // const handleCloseStrategiesModal = () => { setShowStrategiesModal(false); };

  // 处理策略选择变化

  // 确认加载选中的策略 - 直接在Modal组件中使用内联函数
  // const handleConfirmLoadStrategies = () => { ... };

  // 关闭悬浮的策略按钮
  const handleCloseFloatingStrategy = (strategyId: string) => {
    setFloatingStrategies(prev => prev.filter(s => s.id !== strategyId));
  };

  // 拖动相关状态
  const [isDragging, setIsDragging] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  // ECharts实例引用
  const chartRef = useRef<any>(null);

  // 数据更新后自动滚动到最新K线
  useEffect(() => {
    if (chartRef.current && candleData && candleData.length > 0) {
      // 等待下一个渲染周期，确保图表已经更新
      setTimeout(() => {
        const chartInstance = chartRef.current.getEchartsInstance();
        if (chartInstance) {
          // 设置dataZoom组件的范围，使最后一部分数据可见
          chartInstance.dispatchAction({
            type: 'dataZoom',
            start: Math.max(0, 100 - 30), // 显示最后30%的数据
            end: 100
          });
        }
      }, 100);
    }
  }, [candleData]);

  // 处理拖动开始
  const handleDragStart = (e: React.MouseEvent, strategyId: string) => {
    e.stopPropagation();
    setIsDragging(strategyId);
    const strategy = floatingStrategies.find(s => s.id === strategyId);
    if (strategy) {
      setDragOffset({
        x: e.clientX - strategy.position.x,
        y: e.clientY - strategy.position.y
      });
    }
  };

  // 处理拖动
  const handleDrag = (e: MouseEvent) => {
    if (isDragging) {
      setFloatingStrategies(prev => 
        prev.map(strategy => 
          strategy.id === isDragging 
            ? { ...strategy, position: { 
                x: (e as MouseEvent).clientX - dragOffset.x,
                y: (e as MouseEvent).clientY - dragOffset.y 
              } } 
            : strategy
        )
      );
    }
  };

  // 处理拖动结束
  const handleDragEnd = () => {
    setIsDragging(null);
  };

  // 添加鼠标事件监听器来处理拖动
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleDrag as EventListener);
      document.addEventListener('mouseup', handleDragEnd as EventListener);
      return () => {
        document.removeEventListener('mousemove', handleDrag as EventListener);
        document.removeEventListener('mouseup', handleDragEnd as EventListener);
      };
    }
  }, [isDragging, dragOffset]);

  // 打开策略选择对话框
  const openStrategiesModal = () => {
    setShowStrategiesModal(true);
  };

  // 返回组件的JSX结构
  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: '#0F0F1A' }}>
      {/* 左侧市场概览面板 */}
      <div style={{ width: '180px', borderRight: '1px solid #3E3E5A', backgroundColor: '#1E1E2E', overflowY: 'auto' }}>
        <div style={{ padding: '12px 8px', borderBottom: '1px solid #3E3E5A' }}>
          <h3 style={{ color: '#fff', margin: '0 0 8px 0', fontSize: '14px' }}>市场概览</h3>
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              placeholder="搜索..."
              style={{
                width: '100%',
                padding: '4px 8px 4px 24px',
                backgroundColor: '#2E2E4A',
                border: '1px solid #4E4E6A',
                borderRadius: '4px',
                color: '#fff',
                fontSize: '12px',
                boxSizing: 'border-box'
              }}
            />
            <SearchOutlined style={{ position: 'absolute', left: '6px', top: '50%', transform: 'translateY(-50%)', color: '#8E8EA0', fontSize: '12px' }} />
          </div>
          {lastUpdated && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', fontSize: '11px', color: '#6E6E8A', marginTop: '4px' }}>
              上次刷新: {lastUpdated}
              <Button 
                type="text" 
                size="small" 
                style={{ color: '#8E8EA0', fontSize: '12px', marginLeft: '8px' }}
                onClick={async () => {
                  if (symbols.length > 0 && !isRefreshing) {
                    setIsRefreshing(true);
                    try {
                      await loadMarketOverview(symbols);
                      message.success('数据已刷新');
                    } catch (error) {
                      message.error('刷新失败');
                    } finally {
                      setIsRefreshing(false);
                    }
                  }
                }}
                loading={isRefreshing}
              >
                {isRefreshing ? '刷新中...' : '刷新'}
              </Button>
            </div>
          )}
        </div>
        <div style={{ padding: '8px' }}>
          {isLoadingSymbols ? (
            // 加载状态显示
            Array.from({ length: 5 }).map((_, index) => (
              <div key={index} style={{ marginBottom: '8px', padding: '8px', backgroundColor: '#2E2E4A', borderRadius: '4px' }}>
                <div style={{ height: '12px', backgroundColor: '#4E4E6A', borderRadius: '2px', marginBottom: '6px' }}></div>
                <div style={{ height: '10px', backgroundColor: '#4E4E6A', borderRadius: '2px', width: '60%' }}></div>
              </div>
            ))
          ) : (
            marketOverview.map((item) => (
              <div
                key={item.code}
                style={{
                  marginBottom: '4px',
                  padding: '12px 8px', // 增加上下padding约17%以实现整体高度增加约10%
                  backgroundColor: symbol === item.code ? '#3E3E5A' : '#2E2E4A',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  borderLeft: symbol === item.code ? '3px solid #165DFF' : '3px solid transparent'
                }}
                onClick={() => setSymbol(item.code)}
                onMouseEnter={(e) => {
                  if (symbol !== item.code) {
                    e.currentTarget.style.backgroundColor = '#3E3E5A';
                  }
                }}
                onMouseLeave={(e) => {
                  if (symbol !== item.code) {
                    e.currentTarget.style.backgroundColor = '#2E2E4A';
                  }
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ color: '#fff', fontSize: '13px', fontWeight: 'bold', fontFamily: 'monospace' }}>{item.code}</span>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    {item.trend === 'up' ? (
                      <ArrowUpOutlined style={{ color: '#52c41a', fontSize: '12px', marginRight: '2px' }} />
                    ) : item.trend === 'down' ? (
                      <ArrowDownOutlined style={{ color: '#ff4d4f', fontSize: '12px', marginRight: '2px' }} />
                    ) : null}
                    <span style={{ color: item.trend === 'up' ? '#52c41a' : item.trend === 'down' ? '#ff4d4f' : '#8E8EA0', fontSize: '12px' }}>
                      ({item.changePercent}%)
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: '#fff', fontSize: '14px', fontWeight: 'bold' }}>{item.price}</span>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    {item.trend === 'up' ? (
                      <ArrowUpOutlined style={{ color: '#52c41a', fontSize: '12px', marginRight: '2px' }} />
                    ) : item.trend === 'down' ? (
                      <ArrowDownOutlined style={{ color: '#ff4d4f', fontSize: '12px', marginRight: '2px' }} />
                    ) : null}
                    <span style={{ color: item.trend === 'up' ? '#52c41a' : item.trend === 'down' ? '#ff4d4f' : '#8E8EA0', fontSize: '12px' }}>
                      {item.change}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 右侧主内容区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#0F0F1A' }}>
        {/* 顶部工具栏 */}
        <div style={{ padding: '12px 16px', backgroundColor: '#1E1E2E', borderBottom: '1px solid #3E3E5A' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {/* 股票选择器 */}
            <div style={{ marginRight: '16px' }}>
              <Select
                value={symbol}
                onChange={setSymbol}
                style={{ width: '120px', backgroundColor: '#3E3E5A', borderColor: '#4E4E6A' }}
                options={symbols.map(s => ({ label: s.code, value: s.code }))}
                loading={isLoadingSymbols}
                placeholder="选择股票"
                size="small"
                styles={{ popup: { root: { backgroundColor: '#3E3E5A', borderColor: '#4E4E6A' } } }}
                optionFilterProp="label"
                filterOption={(input, option) => {
                  if (!option) return false;
                  return ((option.label as string).toLowerCase().includes(input.toLowerCase())) ||
                    (symbols.find(s => s.code === option.value)?.name.toLowerCase().includes(input.toLowerCase()) || false);
                }}
              />
            </div>

            {/* 股票价格和变动信息 */}
            {selectedSymbolData && (
              <div style={{ display: 'flex', alignItems: 'center', marginRight: 'auto' }}>
                <span style={{ color: '#fff', fontSize: '18px', fontWeight: 'bold', marginRight: '12px' }}>
                  {selectedSymbolData.price}
                </span>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {selectedSymbolData.trend === 'up' ? (
                    <ArrowUpOutlined style={{ color: '#52c41a', marginRight: '4px' }} />
                  ) : selectedSymbolData.trend === 'down' ? (
                    <ArrowDownOutlined style={{ color: '#ff4d4f', marginRight: '4px' }} />
                  ) : null}
                  <span style={{
                    color: selectedSymbolData.trend === 'up' ? '#52c41a' : selectedSymbolData.trend === 'down' ? '#ff4d4f' : '#8E8EA0',
                    fontSize: '14px',
                    marginRight: '4px'
                  }}>
                    {selectedSymbolData.change}
                  </span>
                  <span style={{
                    color: selectedSymbolData.trend === 'up' ? '#52c41a' : selectedSymbolData.trend === 'down' ? '#ff4d4f' : '#8E8EA0',
                    fontSize: '12px'
                  }}>
                    ({selectedSymbolData.changePercent}%)
                  </span>
                </div>
              </div>
            )}

            {/* 策略选择按钮 */}
            <Button
              type="primary"
              size="small"
              onClick={openStrategiesModal}
              style={{ marginLeft: '16px', backgroundColor: '#3E3E5A', borderColor: '#3E3E5A' }}
              icon={<CodeOutlined />}
            >
              选择策略
            </Button>
          </div>
        </div>

        {/* 图表工具栏 */}
        <div style={{ padding: '4px 8px', backgroundColor: '#1E1E2E', display: 'flex', alignItems: 'center', borderBottom: '1px solid #3E3E5A' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {/* 时间周期选择 - 确保所有周期都可用且可点击 */}
            <div style={{ display: 'flex', position: 'relative', zIndex: 10 }}>
              {['1m', '5m', '15m', '30m', '60m', '1h', '4h', '1D', '1W', '1M'].map((period) => (
                <Button
                  key={period}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    setTimeframe(period);
                    // 切换时间周期时清除日期范围
                    setDateRange([null, null]);
                  }}
                  style={{
                    marginRight: '2px',
                    padding: '2px 6px',
                    backgroundColor: timeframe === period ? '#26A69A' : '#2E2E4A',
                    border: 'none',
                    color: '#fff',
                    fontSize: '11px',
                    cursor: 'pointer',
                    pointerEvents: 'auto'
                  }}
                  className="timeframe-button"
                >
                  {period}
                </Button>
              ))}
            </div>
            
            {/* 日期范围选择控件及显示 - 移至周期选择列表后面 */}
            <div style={{ display: 'flex', alignItems: 'center', marginLeft: '8px', position: 'relative' }}>
              {/* 显示当前选择的日期范围，可直接点击触发日历选择器 */}
              <div 
                onClick={() => {
                  setShowDatePicker(!showDatePicker);
                }}
                style={{
                  padding: '2px 8px',
                  backgroundColor: '#1E1E3A',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: dateRange[0] && dateRange[1] ? '#26A69A' : '#888',
                  minWidth: '220px',
                  cursor: 'pointer'
                }}
              >
                {dateRange[0] && dateRange[1] ? 
                  `${dateRange[0].format('YYYY-MM-DD HH:mm')} - ${dateRange[1].format('YYYY-MM-DD HH:mm')}` : 
                  '请选择日期范围'
                }
              </div>
              {showDatePicker && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  zIndex: 1000,
                  backgroundColor: '#3E3E5A',
                  padding: '8px',
                  borderRadius: '4px',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)'
                }}
                onMouseEnter={() => setIsDatePickerFocused(true)}
                onMouseLeave={() => setIsDatePickerFocused(false)}>
                  <DatePicker.RangePicker
                    size="small"
                    value={dateRange}
                    format="YYYY-MM-DD HH:mm"
                    showTime={{ 
                      defaultValue: [
                        dayjs().hour(0).minute(0),
                        dayjs().hour(0).minute(0)
                      ]
                    }}
                    // 禁用未来的时间
                    disabledDate={(current) => {
                      // 禁用今天之后的日期
                      return current && current > dayjs().endOf('day');
                    }}
                    disabledTime={(current) => {
                      // 禁用今天之后的时间
                      if (current && current.isSame(dayjs(), 'day')) {
                        // 允许选择今天的所有时间
                        return { disabledHours: () => [], disabledMinutes: () => [], disabledSeconds: () => [] };
                      }
                      return {};
                    }}
                    onChange={(dates) => {
                      if (dates && dates[0] && dates[1]) {
                        setDateRange([dates[0], dates[1]]);
                        fetchData(dates[0].toDate(), dates[1].toDate());
                        // 选择完成后自动收起日历选择器
                        setShowDatePicker(false);
                      } else {
                        setDateRange([null, null]);
                      }
                    }}
                    className="custom-date-picker"
                  />
                </div>
              )}
            </div>
          </div>
          
          {/* 图表类型选择和显示控制 - 移至最右边 */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginLeft: 'auto' }}>
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
        </div>
        
        {/* 策略按钮区域 - 吸附在首页顶部工具栏下方 */}
        <div style={{ 
          padding: '4px 8px', 
          backgroundColor: '#1E1E2E', 
          height: '32px', 
          display: 'flex', 
          alignItems: 'center',
          gap: '8px',
          overflowX: 'auto',
          position: 'sticky',
          top: 0,
          zIndex: 100,
          borderBottom: '1px solid #3E3E5A'
        }}>
          {floatingStrategies.map((strategy) => {
            // 获取该策略的回测状态
            const backtestState = strategyBacktestStates[strategy.id];
            
            return (
              <div
                key={strategy.id}
                style={{
                  backgroundColor: backtestState?.isRunning ? '#2E4A2E' : backtestState?.hasResults ? '#2E4A4A' : '#2E2E4A',
                  border: `1px solid ${backtestState?.isRunning ? '#4E6A4E' : backtestState?.hasResults ? '#4E6A6A' : '#4E4E6A'}`,
                  borderRadius: '4px',
                  padding: '4px 8px',
                  display: 'flex',
                  alignItems: 'center',
                  cursor: isDragging === strategy.id ? 'grabbing' : 'grab',
                  color: '#fff',
                  fontSize: '12px',
                  whiteSpace: 'nowrap',
                  minWidth: '120px'
                }}
                onMouseDown={(e) => handleDragStart(e, strategy.id)}
              >
                <span style={{ marginRight: '8px', fontSize: '11px' }}>{strategy.name}</span>
                {backtestState && (
                  <span style={{
                    fontSize: '10px',
                    marginRight: '8px',
                    padding: '1px 4px',
                    borderRadius: '2px',
                    backgroundColor: backtestState.isRunning ? '#26A69A' : '#165DFF'
                  }}>
                    {backtestState.isRunning ? '回测中...' : 
                     backtestState.hasResults ? `信号: ${backtestState.signals.length}` : '未回测'}
                  </span>
                )}
                <Button
                  type="text"
                  icon={<CloseOutlined style={{ color: '#fff', fontSize: '10px' }} />}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation(); // 阻止事件冒泡
                    handleCloseFloatingStrategy(strategy.id);
                  }}
                  style={{ padding: '0 4px', marginLeft: 'auto', height: '20px', width: '20px' }}
                />
              </div>
            );
          })}
        </div>
        
        {/* 信号说明区域 */}
        {Object.values(strategyBacktestStates).some(state => state.hasResults && state.signals.length > 0) && (
          <div style={{
            padding: '8px 16px',
            backgroundColor: '#1E1E2E',
            borderBottom: '1px solid #3E3E5A',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            flexWrap: 'wrap'
          }}>
            <span style={{ color: '#8E8EA0', fontSize: '12px' }}>信号说明:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{ width: '12px', height: '12px', color: '#ff4d4f', fontSize: '12px', textAlign: 'center' }}>▼</div>
              <span style={{ color: '#fff', fontSize: '12px' }}>卖出</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{ width: '12px', height: '12px', color: '#52c41a', fontSize: '12px', textAlign: 'center' }}>▲</div>
              <span style={{ color: '#fff', fontSize: '12px' }}>买入</span>
            </div>
          </div>
        )}

        {/* 图表区域 - 自适应高度 */}
        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          {isLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%', backgroundColor: '#0F0F1A' }}>
              <div style={{ color: '#fff' }}>加载中...</div>
            </div>
          ) : (
            <ReactECharts 
              option={chartOption} 
              style={{ height: '100%', width: '100%' }} 
              ref={chartRef} 
            />
          )}
        </div>
      </div>
      
      {/* 策略选择模态框 */}
      <Modal
        title="选择策略"
        open={showStrategiesModal}
        onCancel={() => setShowStrategiesModal(false)}
        onOk={() => {
          // 这里可以添加确认逻辑
          setShowStrategiesModal(false);
        }}
        width={600}
        okText="确定"
        cancelText="取消"
      >
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          {strategiesData.length === 0 ? (
            <div style={{ color: '#fff', textAlign: 'center', padding: '20px' }}>没有可用的策略</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {strategiesData.map((strategy) => (
                <div
                  key={strategy.id}
                  style={{
                    padding: '10px',
                    border: '1px solid #4E4E6A',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    backgroundColor: '#3E3E5A',
                    color: '#fff',
                    cursor: 'pointer'
                  }}
                  onClick={() => {
                    handleAddStrategy(strategy.id, strategy.name);
                    setShowStrategiesModal(false);
                  }}
                >
                  <Checkbox
                    style={{ color: '#fff' }}
                    checked={false}
                    onChange={(e) => e.stopPropagation()}
                  />
                  <span style={{ marginLeft: '10px', flex: 1 }}>{strategy.name}</span>
                  <Button
                    type="text"
                    size="small"
                    onClick={(e) => {
                    e.stopPropagation();
                    handleAddStrategy(strategy.id, strategy.name);
                    setShowStrategiesModal(false);
                  }}
                    style={{ color: '#26A69A' }}
                  >
                    添加
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default Dashboard;