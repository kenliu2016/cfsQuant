/**
 * 价格格式化函数
 * 根据数值大小自动转换为适当的单位（K、M），并智能调整小数位数
 * @param value 要格式化的数值
 * @returns 格式化后的字符串
 */
export const formatPriceWithUnit = (value: number): string => {
  // 处理NaN和Infinity
  if (isNaN(value) || !isFinite(value)) return '0.00';
  
  // 处理负数
  const sign = value < 0 ? '-' : '';
  const absValue = Math.abs(value);
  
  let formattedValue: string = '';
  
  if (absValue >= 1000000) {
    // 大于等于100万，使用M单位
    formattedValue = (absValue / 1000000).toFixed(2) + 'M';
  } else if (absValue >= 1000) {
    // 大于等于1000，使用K单位
    formattedValue = (absValue / 1000).toFixed(2) + 'K';
  } else if (absValue >= 100) {
    // 100-999，保留2位小数
    formattedValue = absValue.toFixed(2);
  } else if (absValue >= 10) {
    // 10-99，保留2位小数
    formattedValue = absValue.toFixed(2);
  } else if (absValue >= 1) {
    // 1-9，保留3位小数
    formattedValue = absValue.toFixed(3);
  } else if (absValue >= 0.01) {
    // 0.01-0.99，保留4位小数
    formattedValue = absValue.toFixed(4);
  } else if (absValue > 0) {
    // 小于0.01的极小值，使用toFixed处理
    formattedValue = absValue.toFixed(6);
  } else {
    // 0值
    formattedValue = '0.00';
  }
  
  // 移除末尾不必要的0和小数点
  formattedValue = formattedValue.replace(/\.?0+$/, '');
  
  // 确保至少有一个小数点和两位小数
  if (!formattedValue.includes('.')) {
    formattedValue += '.00';
  } else {
    const parts = formattedValue.split('.');
    if (parts[1].length < 2) {
      formattedValue = parts[0] + '.' + parts[1].padEnd(2, '0');
    }
  }
  
  // 添加符号并返回
  return sign + formattedValue;
};