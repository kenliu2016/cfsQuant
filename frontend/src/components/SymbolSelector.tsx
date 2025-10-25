import React, { useEffect, useState } from 'react';
import { Select } from 'antd';
import type { SelectProps } from 'antd';
import client from '../api/client';

interface SymbolData {
  symbol: string;
  exchange: string;
  name?: string;
}

interface SymbolSelectorProps extends Omit<SelectProps<string>, 'options' | 'loading' | 'filterOption'> {
  onSymbolsLoaded?: (symbols: SymbolData[]) => void;
}

/**
 * 可复用的Symbol选择器组件
 * 从API获取active=true的market_codes数据
 */
const SymbolSelector: React.FC<SymbolSelectorProps> = ({
  value,
  onChange,
  onSymbolsLoaded,
  ...otherProps
}) => {
  const [symbols, setSymbols] = useState<SymbolData[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 从API获取active状态为true的market_codes
  const fetchActiveSymbolsFromAPI = async () => {
    try {
      const response = await client.get('/api/market/market_codes', {
        params: {
          active: true
        }
      });
      
      // 后端返回的数据结构是 { rows: [{ symbol: string, exchange: string, active: boolean, watch: boolean }] }
      const marketCodes = response.data.rows || [];
      // 将数据转换为前端需要的格式
      return marketCodes.map((item: any) => ({
        symbol: item.symbol,
        exchange: item.exchange,
        name: item.name || '' // 保留name字段用于过滤
      }));
    } catch (error) {
      console.error('Failed to fetch active symbols from API:', error);
      // API调用失败时使用空数组
      return [];
    }
  };

  // 加载symbol数据 - 只在组件挂载时加载一次
  useEffect(() => {
    const loadSymbols = async () => {
      setIsLoading(true);
      try {
        const activeSymbolsData = await fetchActiveSymbolsFromAPI();
        setSymbols(activeSymbolsData);
        // 通知父组件数据已加载
        if (onSymbolsLoaded) {
          onSymbolsLoaded(activeSymbolsData);
        }
      } catch (error) {
        console.error('Error loading symbols:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadSymbols();
  }, []); // 空依赖数组，只在组件挂载时执行一次

  // 删除未使用的filterOption函数

  return (
    <Select
      value={value}
      onChange={onChange}
      style={{
        width: '220px',
        backgroundColor: '#3E3E5A',
        borderColor: '#4E4E6A',
        ...(otherProps.style || {})
      }}
      options={symbols.map(s => ({ 
        label: s.symbol, 
        value: s.symbol,
        name: s.name || ''
      }))}
      loading={isLoading}
      placeholder="选择交易对"
      size="small"
      showSearch={true}
      styles={{
        popup: { root: { backgroundColor: '#FFFFFF', borderColor: '#4E4E6A' } }
      }}
      optionFilterProp="children"
      filterOption={(input, option) => {
        if (!option) return false;
        const lowerInput = input.toLowerCase();
        const symbolMatch = option.label.toLowerCase().includes(lowerInput);
        const nameMatch = option.name ? option.name.toLowerCase().includes(lowerInput) : false;
        return symbolMatch || nameMatch;
      }}
      {...otherProps}
    />
  );
};

export default SymbolSelector;
export type { SymbolData };