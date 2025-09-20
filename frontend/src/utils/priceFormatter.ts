/**
 * 价格格式化函数
 * 根据数值大小自动转换为适当的单位（K、M），并显示4位小数
 * @param value 要格式化的数值
 * @returns 格式化后的字符串
 */
export const formatPriceWithUnit = (value: number): string => {
  // 处理NaN和Infinity
  if (isNaN(value) || !isFinite(value)) return '0.0000';
  
  // 处理负数
  const sign = value < 0 ? '-' : '';
  const absValue = Math.abs(value);
  
  let formattedValue: string = '';
  
  // 所有数值统一显示4位小数
  if (absValue >= 1000000) {
    // 大于等于100万，使用M单位
    formattedValue = (absValue / 1000000).toFixed(4) + 'M';
  } else if (absValue >= 1000) {
    // 大于等于1000，使用K单位
    formattedValue = (absValue / 1000).toFixed(4) + 'K';
  } else {
    // 小于1000，保留4位小数
    formattedValue = absValue.toFixed(4);
  }
  
  // 确保至少有一个小数点和4位小数
  if (!formattedValue.includes('.')) {
    formattedValue += '.0000';
  } else {
    const parts = formattedValue.split('.');
    if (parts[1].length < 4) {
      formattedValue = parts[0] + '.' + parts[1].padEnd(4, '0');
    }
  }
  
  // 添加符号并返回
  return sign + formattedValue;
};