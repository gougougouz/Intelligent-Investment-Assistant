"""
集中管理项目配置参数。

对外暴露：
- AppConfig: 配置数据结构
- Base64Limits: Base64 转码阈值配置类
- load_config(): 从环境变量加载配置

建议通过环境变量配置参数，适用于容器化部署与多环境切换。
"""

from .settings import AppConfig, Base64Limits, load_config, ArkConfig