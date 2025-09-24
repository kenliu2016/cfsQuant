from typing import Protocol, Dict, Any, List
import pandas as pd
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StrategyMetadata:
    """策略元数据"""
    name: str
    description: str
    version: str
    author: str
    created_at: datetime
    updated_at: datetime
    tags: List[str] = None

@dataclass
class StrategyParameters:
    """策略参数定义"""
    name: str
    type: str  # 'float', 'int', 'bool', 'string'
    default: Any
    description: str
    min_value: float = None
    max_value: float = None
    choices: List[Any] = None

class IStrategy(Protocol):
    """策略接口协议"""
    metadata: StrategyMetadata
    parameters: List[StrategyParameters]
    
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """验证策略参数"""
        ...
    
    def run(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """运行策略"""
        ...
    
    def get_indicators(self) -> List[str]:
        """返回策略使用的指标列表"""
        ...
