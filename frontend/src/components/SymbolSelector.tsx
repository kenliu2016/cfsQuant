import React, { useEffect, useState } from 'react';
import { Select } from 'antd';
import type { SelectProps } from 'antd';
import client from '../api/client';

interface SymbolData {
  code: string;
  excode: string;
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
      
      // 假设后端返回的数据结构是 { rows: [{ code: string, exchange: string, excode: string }] }
      const marketCodes = response.data.rows || [];
      // 将数据转换为前端需要的格式
      return marketCodes.map((item: any) => ({
        code: item.excode,
        excode: item.excode, 
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

  // 自定义过滤函数
  const filterOption = (input: string, option?: { label: string; value: string }): boolean => {
    if (!option) return false;
    // 根据输入的关键字过滤选项
    const lowerInput = input.toLowerCase();
    const lowerLabel = option.label.toLowerCase();
    
    // 检查标签是否包含输入的关键字
    const labelMatch = lowerLabel.includes(lowerInput);
    
    // 如果有name属性，也检查name是否包含输入的关键字
    const symbolInfo = symbols.find(s => s.code === option.value);
    const nameMatch = !!(symbolInfo && symbolInfo.name && 
                    symbolInfo.name.toLowerCase().includes(lowerInput));
    
    return labelMatch || nameMatch;
  };

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
      options={symbols.map(s => ({ label: s.code, value: s.code }))}
      loading={isLoading}
      placeholder="选择股票"
      size="small"
      showSearch={true}
      styles={{
        popup: { root: { backgroundColor: '#FFFFFF', borderColor: '#4E4E6A' } }
      }}
      optionFilterProp="label"
      filterOption={filterOption}
      {...otherProps}
    />
  );
};

export default SymbolSelector;
export type { SymbolData };