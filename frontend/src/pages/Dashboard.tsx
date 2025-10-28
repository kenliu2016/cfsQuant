// ... existing code ...

// 清理未使用的导入
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Tag, Segmented, Progress, Table, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SyncOutlined, SettingOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
// import client from '../api/client'; // 删除未使用的导入
import {
  getDashboardSummary,
  getEnhancedStrongWeakCoins,
  getMarketBaseScore,
  type StrongWeakCoin,
  type EnhancedStrongWeakCoin,
  type CoinAnalysisItem,
  // type MarketSentiment // 删除未使用的导入
} from '../api/dashboardOptimized';
import styles from './Dashboard.module.css';

type TrendCoin = {
  symbol: string;
  pair: string;
  change24h: number;
  vmr: number;
  composite: number;
  spark: number[];
};

// 删除重复的类型定义，使用从API导入的EnhancedStrongWeakCoin类型

// 删除未使用的类型定义
// type EnhancedStrongWeakCoinsResponse = {
//   success: boolean;
//   data: {
//     strong_coins: EnhancedStrongWeakCoin[];
//     weak_coins: EnhancedStrongWeakCoin[];
//   };
//   message: string;
// };

type CoinAnalysisTableItem = CoinAnalysisItem & {
  // 为了兼容现有代码，添加别名字段
  quoteVolume?: number; // 对应volume_24h，改为可选字段
  ve?: number; // 对应ve_value，改为可选字段
};

// type CoinAnalysisTableResponse = {
//   success: boolean;
//   data: {
//     items: CoinAnalysisTableItem[];
//     pagination: {
//       page: number;
//       page_size: number;
//       total_count: number;
//       total_pages: number;
//       has_previous: boolean;
//       has_next: boolean;
//     };
//   };
//   message: string;
// };

// type CoinTableRow = {
//   key: string;
//   symbol: string;
//   pair: string;
//   marketCap: string;
//   volume24h: string;
//   vmr: number;
//   l1: number;
//   ve: number;
//   composite: number;
//   forecast: number;
// };

type MarketMetrics = {
  bullBearScore: number;
  bullBearPhase: string;
  bullBearUpdatedAt?: string;
  fearGreedValue: number;
  fearGreedClassification?: string;
  fearGreedUpdatedAt?: string;
};

// type MarketBaseScoreResponse = {
//   bull_bear?: {
//     score?: number;
//     phase?: string;
//     updated_at?: string;
//     exchange?: string;
//     symbol?: string;
//   };
//   fear_greed?: {
//     value?: number;
//     classification?: string;
//     updated_at?: string;
//   };
// };



// 删除未使用的变量
// const strongCoins: TrendCoin[] = [
//   { symbol: 'SUI', pair: 'SUI-USDT', change24h: 2.95, vmr: 1.66, composite: 0.469, spark: [4, 7, 9, 8, 12, 18, 22] },
//   { symbol: 'UNI', pair: 'UNI-USDT', change24h: 2.69, vmr: 1.09, composite: 0.505, spark: [9, 11, 10, 12, 13, 15, 17] },
//   { symbol: 'VET', pair: 'VET-USDT', change24h: 1.68, vmr: 1.54, composite: 0.486, spark: [6, 7, 8, 8, 10, 11, 12] },
// ];

// const weakCoins: TrendCoin[] = [
//   { symbol: 'CHZ', pair: 'CHZ-USDT', change24h: -4.57, vmr: 1.60, composite: 1.072, spark: [18, 16, 14, 11, 9, 6, 4] },
//   { symbol: 'INJ', pair: 'INJ-USDT', change24h: -3.31, vmr: 1.64, composite: 0.575, spark: [17, 15, 12, 10, 8, 6, 5] },
//   { symbol: 'AXS', pair: 'AXS-USDT', change24h: -2.91, vmr: 0.88, composite: 0.576, spark: [15, 14, 12, 11, 9, 7, 6] },
// ];



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
  const [coinAnalysisLoading, setCoinAnalysisLoading] = useState(false);
  const [coinAnalysisPagination, setCoinAnalysisPagination] = useState({
    page: 1,
    page_size: 10,
    total_count: 0,
    total_pages: 0,
    has_previous: false,
    has_next: false
  });

  const fetchDashboardData = useCallback(async () => {
    setRefreshing(true);
    setCoinsLoading(true);
    setCoinAnalysisLoading(true);
    
    try {
      // 并行获取Dashboard汇总数据、增强版强势弱势币种数据和原始市场情绪数据
      const [dashboardSummary, enhancedCoinsData, marketBaseScore] = await Promise.all([
        getDashboardSummary(),
        getEnhancedStrongWeakCoins(),
        getMarketBaseScore()
      ]);
      
      // 设置市场情绪数据 - 使用原始数据API获取的数据
      setMarketMetrics({
        bullBearScore: marketBaseScore.bull_bear.score,
        bullBearPhase: marketBaseScore.bull_bear.phase,
        bullBearUpdatedAt: marketBaseScore.bull_bear.updated_at,
        fearGreedValue: marketBaseScore.fear_greed.value,
        fearGreedClassification: marketBaseScore.fear_greed.classification,
        fearGreedUpdatedAt: marketBaseScore.fear_greed.updated_at,
      });
      
      // 使用增强版API数据设置强势弱势币种数据（包含小时数据用于缩略图）
      const top5StrongCoins: EnhancedStrongWeakCoin[] = enhancedCoinsData.strong_coins.slice(0, 5);
      const top5WeakCoins: EnhancedStrongWeakCoin[] = enhancedCoinsData.weak_coins.slice(0, 5);
      
      setStrongCoins(top5StrongCoins || []);
      setWeakCoins(top5WeakCoins || []);
      
      // 设置币种分析表数据
      const tableData: CoinAnalysisTableItem[] = dashboardSummary.coin_analysis.map(coin => ({
        ...coin,
        quoteVolume: coin.volume_24h, // 映射volume_24h到quoteVolume
        ve: coin.ve_value // 映射ve_value到ve
      }));
      
      setCoinAnalysisData(tableData || []);
      setCoinAnalysisPagination({
        page: 1,
        page_size: 10,
        total_count: dashboardSummary.coin_analysis.length,
        total_pages: Math.ceil(dashboardSummary.coin_analysis.length / 10),
        has_previous: false,
        has_next: dashboardSummary.coin_analysis.length > 10
      });
      
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
      title: 'VMR ↑',
      dataIndex: 'vmr_total',
      key: 'vmr_total',
      render: (value) => <span className={styles.tableValue}>{value ? value.toFixed(6) : '0.000000'}</span>,
    },
    {
      title: 'VE ↑',
      dataIndex: 've_value',
      key: 've_value',
      render: (value) => <span className={styles.tableValue}>{value ? value.toFixed(6) : '0.000000'}</span>,
    },
    {
      title: '复合分数',
      dataIndex: 'composite_score',
      key: 'composite_score',
      render: (value) => <span className={styles.tableValue}>{value ? value.toFixed(6) : '0.000000'}</span>,
    },
  ], []);

  const handleRefresh = () => {
    fetchDashboardData();
  };

  const handleCoinAnalysisTableChange = useCallback((page: number, pageSize: number) => {
    // 由于使用汇总接口，分页在客户端处理
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginatedData = coinAnalysisData.slice(startIndex, endIndex);
    
    setCoinAnalysisData(paginatedData);
    setCoinAnalysisPagination({
      page,
      page_size: pageSize,
      total_count: coinAnalysisData.length,
      total_pages: Math.ceil(coinAnalysisData.length / pageSize),
      has_previous: page > 1,
      has_next: page < Math.ceil(coinAnalysisData.length / pageSize)
    });
  }, [coinAnalysisData]);

  // 将API返回的EnhancedStrongWeakCoin数据转换为前端需要的TrendCoin格式
  // 修复convertToTrendCoin函数中的类型错误
  const convertToTrendCoin = (coin: EnhancedStrongWeakCoin): TrendCoin => {
    return {
      symbol: coin.symbol,
      pair: coin.symbol + '-USDT',
      change24h: coin.gain_24h || 0, // 处理undefined情况
      vmr: coin.vmr_total || 0, // 使用vmr_total字段作为VMR值
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
              <div className={styles.sectionDescription}>Top 300 币种 | 排除稳定币 | 市值 &gt; $100M | 支持多列排序与筛选</div>
            </div>
            <div className={styles.tableMeta}>
              <span>实时样本: 32</span>
              <span className={styles.separatorDot} />
              <span>更新时间: 04:06</span>
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
    </div>
  );
};

export default Dashboard;
