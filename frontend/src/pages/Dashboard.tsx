import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Tag, Segmented, Progress, Table, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SyncOutlined, SettingOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import client from '../api/client';
import styles from './Dashboard.module.css';

type TrendCoin = {
  symbol: string;
  pair: string;
  change24h: number;
  vmr: number;
  composite: number;
  spark: number[];
};

type CoinTableRow = {
  key: string;
  symbol: string;
  pair: string;
  marketCap: string;
  volume24h: string;
  vmr: number;
  l1: number;
  ve: number;
  composite: number;
  forecast: number;
};

type MarketMetrics = {
  bullBearScore: number;
  bullBearPhase: string;
  bullBearUpdatedAt?: string;
  fearGreedValue: number;
  fearGreedClassification?: string;
  fearGreedUpdatedAt?: string;
};

type MarketBaseScoreResponse = {
  bull_bear?: {
    score?: number;
    phase?: string;
    updated_at?: string;
    exchange?: string;
    symbol?: string;
  };
  fear_greed?: {
    value?: number;
    classification?: string;
    updated_at?: string;
  };
};

const strongCoins: TrendCoin[] = [
  { symbol: 'SUI', pair: 'SUI-USDT', change24h: 2.95, vmr: 1.66, composite: 0.469, spark: [4, 7, 9, 8, 12, 18, 22] },
  { symbol: 'UNI', pair: 'UNI-USDT', change24h: 2.69, vmr: 1.09, composite: 0.505, spark: [9, 11, 10, 12, 13, 15, 17] },
  { symbol: 'VET', pair: 'VET-USDT', change24h: 1.68, vmr: 1.54, composite: 0.486, spark: [6, 7, 8, 8, 10, 11, 12] },
];

const weakCoins: TrendCoin[] = [
  { symbol: 'CHZ', pair: 'CHZ-USDT', change24h: -4.57, vmr: 1.60, composite: 1.072, spark: [18, 16, 14, 11, 9, 6, 4] },
  { symbol: 'INJ', pair: 'INJ-USDT', change24h: -3.31, vmr: 1.64, composite: 0.575, spark: [17, 15, 12, 10, 8, 6, 5] },
  { symbol: 'AXS', pair: 'AXS-USDT', change24h: -2.91, vmr: 0.88, composite: 0.576, spark: [15, 14, 12, 11, 9, 7, 6] },
];

const tableData: CoinTableRow[] = [
  { key: 'CHZ', symbol: 'CHZ', pair: 'CHZ-USDT', marketCap: '$1.80B', volume24h: '$28.87M', vmr: 1.604, l1: 2.9974, ve: 1.072, composite: 1.072, forecast: 2.9566 },
  { key: 'AXS', symbol: 'AXS', pair: 'AXS-USDT', marketCap: '$2.40B', volume24h: '$21.08M', vmr: 0.878, l1: 2.5404, ve: 0.860, composite: 0.860, forecast: 2.5307 },
  { key: 'VET', symbol: 'VET', pair: 'VET-USDT', marketCap: '$3.50B', volume24h: '$54.06M', vmr: 1.544, l1: 1.8627, ve: 0.806, composite: 0.806, forecast: 1.6756 },
  { key: 'GALA', symbol: 'GALA', pair: 'GALA-USDT', marketCap: '$2.10B', volume24h: '$30.73M', vmr: 1.463, l1: 1.2916, ve: 0.718, composite: 0.718, forecast: 1.3064 },
  { key: 'INJ', symbol: 'INJ', pair: 'INJ-USDT', marketCap: '$6.50B', volume24h: '$106.89M', vmr: 1.645, l1: 0.4783, ve: 0.575, composite: 0.575, forecast: 0.4746 },
  { key: 'ARB', symbol: 'ARB', pair: 'ARB-USDT', marketCap: '$8.80B', volume24h: '$95.77M', vmr: 1.088, l1: 0.8448, ve: 0.565, composite: 0.565, forecast: 0.8669 },
  { key: 'UNI', symbol: 'UNI', pair: 'UNI-USDT', marketCap: '$12.00B', volume24h: '$130.67M', vmr: 1.089, l1: 0.5827, ve: 0.505, composite: 0.505, forecast: 0.5695 },
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

  const fetchMarketMetrics = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await client.get<MarketBaseScoreResponse>('/api/market/market-base-score');
      const payload = response.data ?? {};
      setMarketMetrics({
        bullBearScore: Number(payload.bull_bear?.score ?? 0),
        bullBearPhase: payload.bull_bear?.phase || 'Neutral',
        bullBearUpdatedAt: payload.bull_bear?.updated_at,
        fearGreedValue: Number(payload.fear_greed?.value ?? 0),
        fearGreedClassification: payload.fear_greed?.classification || undefined,
        fearGreedUpdatedAt: payload.fear_greed?.updated_at,
      });
    } catch (error) {
      console.error('Failed to fetch market base score', error);
      message.error('获取市场情绪数据失败');
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchMarketMetrics();
  }, [fetchMarketMetrics]);

  const biasScore = marketMetrics.bullBearScore ?? 0;
  const clampedScore = clamp(biasScore, -7, 7);
  const gaugePercent = ((clampedScore + 7) / 14) * 100;
  const fearGreedValue = clamp(marketMetrics.fearGreedValue ?? 0, 0, 100);

  const columns: ColumnsType<CoinTableRow> = useMemo(() => [
    {
      title: '币种',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (_, record) => (
        <div className={styles.coinCell}>
          <div className={styles.coinSymbol}>{record.symbol}</div>
          <div className={styles.coinPair}>{record.pair}</div>
        </div>
      ),
    },
    {
      title: '市值',
      dataIndex: 'marketCap',
      key: 'marketCap',
      render: (value) => <span className={styles.tableValue}>{value}</span>,
    },
    {
      title: '24h 成交量',
      dataIndex: 'volume24h',
      key: 'volume24h',
      render: (value) => <span className={styles.tableValue}>{value}</span>,
    },
    {
      title: 'VMR ↑',
      dataIndex: 'vmr',
      key: 'vmr',
      render: (value) => <span className={styles.tableValue}>{value.toFixed(3)}</span>,
    },
    {
      title: 'L1 ↑',
      dataIndex: 'l1',
      key: 'l1',
      render: (value) => <span className={styles.tableValue}>{value.toFixed(4)}</span>,
    },
    {
      title: 'VE ↑',
      dataIndex: 've',
      key: 've',
      render: (value) => <span className={styles.tableValue}>{value.toFixed(3)}</span>,
    },
    {
      title: '复合分数 ↓',
      dataIndex: 'composite',
      key: 'composite',
      render: (value) => (
        <span
          className={
            value > 0.9
              ? styles.compositePositive
              : value > 0.6
                ? styles.compositeNeutral
                : styles.compositeNegative
          }
        >
          {value.toFixed(3)}
        </span>
      ),
    },
    {
      title: '预测 VE ↑',
      dataIndex: 'forecast',
      key: 'forecast',
      render: (value) => <span className={styles.tableValue}>{value.toFixed(4)}</span>,
    },
  ], []);

  const handleRefresh = () => {
    fetchMarketMetrics();
  };

  const renderTrendList = (items: TrendCoin[], trend: 'bullish' | 'bearish') => (
    <ul className={styles.trendList}>
      {items.map((coin) => (
        <li key={coin.symbol} className={styles.trendItem}>
          <div className={styles.trendSymbol}>
            <div className={styles.symbolCircle}>{coin.symbol.slice(0, 2)}</div>
            <div>
              <div className={styles.symbolLabel}>{coin.symbol}</div>
              <div className={styles.symbolPair}>{coin.pair}</div>
            </div>
          </div>
          <div>
            <Sparkline
              data={coin.spark}
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
                {coin.change24h > 0 ? '+' : ''}
                {coin.change24h.toFixed(2)}%
              </span>
              <span className={styles.vmrLabel}>VMR</span>
              <span className={styles.vmrValue}>{coin.vmr.toFixed(3)}</span>
              <span className={styles.vmrLabel}>复合</span>
              <span className={styles.vmrValue}>{coin.composite.toFixed(3)}</span>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );

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
              <div className={styles.sectionDescription}>多因子评分靠前的币种 · 支持 Top 20</div>
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
              dataSource={tableData}
              pagination={false}
              size="small"
              rowClassName={() => styles.tableRow}
            />
          </div>
        </div>

        <div className={`${styles.sectionCard} ${styles.trendCard}`}>
          <div className={styles.trendHeader}>
            <div>
              <div className={styles.sectionTitle}>弱势币种</div>
              <div className={styles.sectionDescription}>下行动能显著 · 风险敞口警示</div>
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
