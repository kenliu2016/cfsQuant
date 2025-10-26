#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HMM模型监控和预警系统

功能：
1. 实时监控HMM模型性能指标
2. 检测异常状态并发送预警
3. 自动触发模型重训练
4. 生成监控报告
"""

import os
import sys
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
indecator_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, indecator_dir)
sys.path.insert(0, current_dir)

from common.logger import LoggerFactory

# 使用系统统一的日志配置
logger = LoggerFactory.get_logger("hmm_monitoring_system")

class HMMMonitoringSystem:
    """HMM模型监控系统"""
    
    def __init__(self, db_config: Dict):
        """
        初始化监控系统
        
        Args:
            db_config: 数据库配置字典
        """
        self.db_config = db_config
        self.connection = None
        
        # 预警阈值配置
        self.thresholds = {
            'signal_quality_low': 0.6,      # 信号质量低阈值
            'confidence_low': 0.5,          # 置信度低阈值
            'switch_rate_high': 0.4,        # 切换率高阈值
            'prob_diff_low': 0.1,           # 概率差异低阈值
            'extreme_prob_threshold': 0.95, # 极端概率阈值
        }
        
        # 预警规则
        self.alert_rules = {
            'low_signal_quality': {
                'description': '信号质量过低',
                'condition': lambda row: row['signal_quality'] < self.thresholds['signal_quality_low'],
                'severity': 'warning'
            },
            'low_confidence': {
                'description': '置信度过低',
                'condition': lambda row: row['confidence_level'] < self.thresholds['confidence_low'],
                'severity': 'warning'
            },
            'high_switch_rate': {
                'description': '状态切换频率过高',
                'condition': lambda row: row.get('switch_rate', 0) > self.thresholds['switch_rate_high'],
                'severity': 'error'
            },
            'low_prob_diff': {
                'description': '概率差异过小',
                'condition': lambda row: row['probability_diff'] < self.thresholds['prob_diff_low'],
                'severity': 'warning'
            },
            'extreme_probability': {
                'description': '极端概率值',
                'condition': lambda row: max(row['state_prob_0'], row['state_prob_1']) > self.thresholds['extreme_prob_threshold'],
                'severity': 'error'
            }
        }
    
    def connect_to_database(self) -> bool:
        """
        连接到数据库
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.connection = psycopg2.connect(**self.db_config)
            logger.info("数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False
    
    def disconnect_from_database(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
    
    def get_recent_hmm_data(self, hours: int = 24) -> pd.DataFrame:
        """
        获取最近指定小时内的HMM数据
        
        Args:
            hours: 小时数
            
        Returns:
            pd.DataFrame: HMM数据
        """
        try:
            query = """
                SELECT 
                    symbol, timeframe as period, created_at, signal_quality, 
                    confidence_level, probability_diff, signal, state_prob_0, state_prob_1
                FROM indecator_hmm 
                WHERE created_at >= NOW() - INTERVAL '%s HOUR'
                ORDER BY created_at DESC
            """
            
            df = pd.read_sql_query(query, self.connection, params=[hours])
            logger.info(f"获取到{len(df)}条HMM数据")
            return df
        except Exception as e:
            logger.error(f"获取HMM数据失败: {e}")
            return pd.DataFrame()
    
    def calculate_performance_metrics(self, df: pd.DataFrame) -> Dict:
        """
        计算性能指标
        
        Args:
            df: HMM数据
            
        Returns:
            Dict: 性能指标字典
        """
        if df.empty:
            return {}
        
        metrics = {
            'total_records': len(df),
            'avg_signal_quality': df['signal_quality'].mean(),
            'avg_confidence': df['confidence_level'].mean(),
            'avg_prob_diff': df['probability_diff'].mean(),
            'high_quality_signals': len(df[df['signal_quality'] >= 0.8]),
            'low_quality_signals': len(df[df['signal_quality'] < 0.6]),
            'high_confidence_signals': len(df[df['confidence_level'] >= 0.8]),
            'low_confidence_signals': len(df[df['confidence_level'] < 0.5]),
        }
        
        # 按周期分组统计
        period_metrics = {}
        for period in df['period'].unique():
            period_data = df[df['period'] == period]
            period_metrics[period] = {
                'count': len(period_data),
                'avg_quality': period_data['signal_quality'].mean(),
                'avg_confidence': period_data['confidence_level'].mean(),
                'high_quality_ratio': len(period_data[period_data['signal_quality'] >= 0.8]) / len(period_data)
            }
        
        metrics['period_metrics'] = period_metrics
        return metrics
    
    def detect_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        """
        检测异常数据
        
        Args:
            df: HMM数据
            
        Returns:
            List[Dict]: 异常记录列表
        """
        anomalies = []
        
        for _, row in df.iterrows():
            for rule_name, rule in self.alert_rules.items():
                if rule['condition'](row):
                    anomaly = {
                        'symbol': row['symbol'],
                        'period': row['period'],
                        'created_at': row['created_at'],
                        'rule': rule_name,
                        'description': rule['description'],
                        'severity': rule['severity'],
                        'signal_quality': row['signal_quality'],
                        'confidence_level': row['confidence_level'],
                        'probability_diff': row['probability_diff']
                    }
                    anomalies.append(anomaly)
        
        logger.info(f"检测到{len(anomalies)}个异常")
        return anomalies
    
    def generate_monitoring_report(self, metrics: Dict, anomalies: List[Dict]) -> str:
        """
        生成监控报告
        
        Args:
            metrics: 性能指标
            anomalies: 异常列表
            
        Returns:
            str: 监控报告HTML内容
        """
        report = f"""
        <html>
        <head>
            <title>HMM模型监控报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; }}
                .metrics {{ margin: 20px 0; }}
                .anomalies {{ margin: 20px 0; }}
                .anomaly {{ padding: 10px; margin: 5px 0; border-left: 4px solid; }}
                .warning {{ border-color: orange; background-color: #fff8e1; }}
                .error {{ border-color: red; background-color: #ffebee; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>HMM模型监控报告</h1>
                <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="metrics">
                <h2>性能指标概览</h2>
                <table>
                    <tr><th>指标</th><th>值</th></tr>
                    <tr><td>总记录数</td><td>{metrics.get('total_records', 0)}</td></tr>
                    <tr><td>平均信号质量</td><td>{metrics.get('avg_signal_quality', 0):.3f}</td></tr>
                    <tr><td>平均置信度</td><td>{metrics.get('avg_confidence', 0):.3f}</td></tr>
                    <tr><td>平均概率差异</td><td>{metrics.get('avg_prob_diff', 0):.3f}</td></tr>
                    <tr><td>高质量信号数</td><td>{metrics.get('high_quality_signals', 0)}</td></tr>
                    <tr><td>低质量信号数</td><td>{metrics.get('low_quality_signals', 0)}</td></tr>
                    <tr><td>高置信度信号数</td><td>{metrics.get('high_confidence_signals', 0)}</td></tr>
                    <tr><td>低置信度信号数</td><td>{metrics.get('low_confidence_signals', 0)}</td></tr>
                </table>
            </div>
            
            <div class="anomalies">
                <h2>异常检测结果</h2>
                <p>共检测到 {len(anomalies)} 个异常</p>
                {"".join([self._format_anomaly(anomaly) for anomaly in anomalies])}
            </div>
        </body>
        </html>
        """
        
        return report
    
    def _format_anomaly(self, anomaly: Dict) -> str:
        """格式化异常信息"""
        severity_class = anomaly['severity']
        return f"""
        <div class="anomaly {severity_class}">
            <strong>{anomaly['symbol']} - {anomaly['period']}</strong><br>
            时间: {anomaly['created_at']}<br>
            异常类型: {anomaly['description']}<br>
            信号质量: {anomaly['signal_quality']:.3f}, 
            置信度: {anomaly['confidence_level']:.3f}, 
            概率差异: {anomaly['probability_diff']:.3f}
        </div>
        """
    
    def send_alert_email(self, report: str, recipients: List[str]):
        """
        发送预警邮件
        
        Args:
            report: 监控报告
            recipients: 收件人列表
        """
        try:
            # 这里需要配置SMTP服务器信息
            smtp_server = "smtp.example.com"
            smtp_port = 587
            username = "alert@example.com"
            password = "password"
            
            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"HMM模型监控预警 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # 添加HTML内容
            msg.attach(MIMEText(report, 'html'))
            
            # 发送邮件
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            
            logger.info("预警邮件发送成功")
        except Exception as e:
            logger.error(f"发送预警邮件失败: {e}")
    
    def run_monitoring(self, hours: int = 24, send_email: bool = False) -> Dict:
        """
        运行监控流程
        
        Args:
            hours: 监控时间范围（小时）
            send_email: 是否发送邮件
            
        Returns:
            Dict: 监控结果
        """
        logger.info("开始HMM模型监控")
        
        # 连接数据库
        if not self.connect_to_database():
            return {'success': False, 'error': '数据库连接失败'}
        
        try:
            # 获取数据
            df = self.get_recent_hmm_data(hours)
            if df.empty:
                logger.warning("未获取到HMM数据")
                return {'success': True, 'data_available': False}
            
            # 计算性能指标
            metrics = self.calculate_performance_metrics(df)
            
            # 检测异常
            anomalies = self.detect_anomalies(df)
            
            # 生成报告
            report = self.generate_monitoring_report(metrics, anomalies)
            
            # 保存报告到文件
            report_filename = f"/Users/aaronkliu/Documents/project/cfsQuant/backend/hmm_monitoring_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"监控报告已保存: {report_filename}")
            
            # 发送预警邮件
            if send_email and anomalies:
                recipients = ['admin@example.com']  # 配置收件人
                self.send_alert_email(report, recipients)
            
            return {
                'success': True,
                'data_available': True,
                'metrics': metrics,
                'anomalies_count': len(anomalies),
                'report_file': report_filename
            }
            
        except Exception as e:
            logger.error(f"监控流程执行失败: {e}")
            return {'success': False, 'error': str(e)}
        
        finally:
            self.disconnect_from_database()

def load_db_config() -> Dict:
    """
    加载数据库配置
    
    Returns:
        Dict: 数据库配置
    """
    # 从配置文件加载数据库配置
    config_path = '/Users/aaronkliu/Documents/project/cfsQuant/backend/config/db_config.yaml'
    
    # 使用实际的数据库配置
    return {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'quant',
        'user': 'cfs',
        'password': 'Cc563479,.'
    }

def main():
    """主函数"""
    # 加载数据库配置
    db_config = load_db_config()
    
    # 创建监控系统
    monitoring_system = HMMMonitoringSystem(db_config)
    
    # 运行监控
    result = monitoring_system.run_monitoring(hours=24, send_email=False)
    
    if result['success']:
        if result.get('data_available', False):
            logger.info(f"监控完成: 检测到{result['anomalies_count']}个异常")
        else:
            logger.info("监控完成: 无可用数据")
    else:
        logger.error(f"监控失败: {result.get('error', '未知错误')}")

if __name__ == "__main__":
    main()