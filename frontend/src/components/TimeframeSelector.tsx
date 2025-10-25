import React from 'react';
import { Select } from 'antd';
import type { SelectProps } from 'antd';

const { Option } = Select;

interface TimeframeSelectorProps extends Omit<SelectProps<string>, 'options' | 'children'> {
  // 可以添加自定义属性
}

/**
 * 可复用的时间间隔选择器组件
 * 提供标准的时间间隔选项：1分钟、5分钟、15分钟、30分钟、60分钟、1小时、4小时、1天、1周、1月
 */
const TimeframeSelector: React.FC<TimeframeSelectorProps> = ({
  ...otherProps
}) => {
  return (
    <Select
      style={{ width: '100%' }}
      {...otherProps}
    >
      <Option value="1m">1分钟</Option>
      <Option value="3m">3分钟</Option>
      <Option value="5m">5分钟</Option>
      <Option value="15m">15分钟</Option>
      <Option value="30m">30分钟</Option>
      <Option value="1h">1小时</Option>
      <Option value="2h">2小时</Option>
      <Option value="4h">4小时</Option>
      <Option value="1d">1天</Option>
      <Option value="2d">2天</Option>
      <Option value="3d">3天</Option>
    </Select>
  );
};

export default TimeframeSelector;