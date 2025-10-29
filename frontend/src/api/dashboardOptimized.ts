/**
 * Dashboard优化API服务
 * 对接后端优化后的高性能Dashboard接口
 */

import client from './client';

// 增强版强势弱势币种数据结构（包含小时数据用于缩略图）
export interface EnhancedStrongWeakCoin {
  symbol: string;
  current_price: number;
  gain_24h: number;
  vmr: number;
  vmr_total?: number; // 添加vmr_total字段，用于兼容Dashboard.tsx
  composite_score?: number; // 添加composite_score字段，用于兼容Dashboard.tsx
  hourly_data?: {
    close: number;
    quote_volume: number;
    timestamp: string;
  }[];
}

// 增强版强势弱势币种响应数据结构
export interface EnhancedStrongWeakCoinsResponse {
  strong_coins: EnhancedStrongWeakCoin[];
  weak_coins: EnhancedStrongWeakCoin[];
}

// 币种分析表数据结构
export interface CoinAnalysisItem {
  symbol: string;
  current_price: number;
  market_cap: number;
  volume_24h: number;
  vmr: number;
  ve_value: number;
  actual_volatility: number;
  composite_score: number;
  rank: number;
  watch?: boolean; // 是否监控的币种
}

// Dashboard汇总数据结构
export interface DashboardSummary {
  strong_coins: EnhancedStrongWeakCoin[];
  weak_coins: EnhancedStrongWeakCoin[];
  coin_analysis: CoinAnalysisItem[];
  market_sentiment: {
    total_coins: number;
    rising_coins: number;
    falling_coins: number;
    avg_gain_24h: number;
    bull_bear_score: number;
    fear_greed_index: number;
    last_updated: string;
  };
  last_updated: string;
  data_source: string;
}

/**
 * 获取Dashboard汇总数据（优化版本）
 * 一次性返回所有dashboard需要的数据，减少HTTP请求开销
 */
export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  const response = await client.get<any>('/api/v1/dashboard/summary');
  
  // 映射后端返回的字段到前端期望的字段
  const data = response.data;
  
  // 映射强势弱势币种数据，后端API现在直接返回gain_24h字段
  const mappedStrongCoins = data.strong_coins?.map((coin: any) => ({
    symbol: coin.symbol,
    current_price: coin.current_price,
    gain_24h: coin.gain_24h, // 直接使用gain_24h字段
    vmr: coin.vmr_24h, // 映射vmr_24h到vmr
    vmr_total: coin.vmr_24h, // 设置vmr_total字段
    composite_score: coin.composite_score || 0, // 设置默认值
    hourly_data: coin.hourly_data // 添加小时数据用于缩略图
  })) || [];
  
  const mappedWeakCoins = data.weak_coins?.map((coin: any) => ({
    symbol: coin.symbol,
    current_price: coin.current_price,
    gain_24h: coin.gain_24h, // 直接使用gain_24h字段
    vmr: coin.vmr_24h, // 映射vmr_24h到vmr
    vmr_total: coin.vmr_24h, // 设置vmr_total字段
    composite_score: coin.composite_score || 0, // 设置默认值
    hourly_data: coin.hourly_data // 添加小时数据用于缩略图
  })) || [];
  
  // 映射币种分析数据
  const mappedCoinAnalysis = data.coin_analysis?.map((coin: any) => ({
    symbol: coin.symbol,
    current_price: coin.current_price,
    market_cap: coin.market_cap,
    volume_24h: coin.volume_24h,
    vmr: coin.vmr_24h,
    ve_value: coin.ve_value,
    actual_volatility: coin.actual_volatility,
    composite_score: coin.composite_score,
    rank: coin.rank
  })) || [];
  
  return {
    strong_coins: mappedStrongCoins,
    weak_coins: mappedWeakCoins,
    coin_analysis: mappedCoinAnalysis,
    market_sentiment: data.market_sentiment,
    last_updated: data.last_updated,
    data_source: data.data_source
  };
};

// VMR时间序列数据点接口
interface VmrDataPoint {
  datetime: string;
  vmr: number;
  return_pct: number;
}

// VMR时间序列接口
interface VmrSeriesItem {
  symbol: string;
  data: VmrDataPoint[];
}

// VMR时间序列响应接口
export interface VmrSeriesResponse {
  series: VmrSeriesItem[];
  timeframe: string;
  symbols: string[];
  total_count: number;
  error?: string;
}

/**
 * 获取VMR时间序列数据
 * 根据时间框架和币种符号获取VMR历史数据
 * 
 * @param timeframe 时间框架（30m, 1h, 4h, 1d, 3d）
 * @param symbols 币种符号列表，为空则获取所有watch=true且quotecurrency=USDT的币种
 * @param limit 返回记录数量限制，默认100
 */
export const getVmrSeries = async (
  timeframe: string,
  symbols?: string[],
  limit: number = 100
): Promise<VmrSeriesResponse> => {
  const params: any = {
    timeframe,
    limit
  };
  
  if (symbols && symbols.length > 0) {
    params.symbols = symbols.join(',');
  }
  
  const response = await client.get<VmrSeriesResponse>('/api/v1/dashboard/vmr-series', { params });
  return response.data;
};