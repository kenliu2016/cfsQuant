import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Tag, Segmented, Progress, Table, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SyncOutlined, SettingOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
// import client from '../api/client'; // 删除未使用的导入
import {
  getDashboardSummary,
  type EnhancedStrongWeakCoin,
  type CoinAnalysisItem,
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
    </div>
  );
};

export default Dashboard;
