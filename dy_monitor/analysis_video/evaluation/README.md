# Evaluation

这个目录用于专门做测评，不和主业务流程混在一起。

## 实验目标

1. 验证历史极值可以由最近一周样本自动标定，而不是人工主观给定。
2. 验证在正常场景和极端故障场景下，系统仍然可以连续产出可用的投资建议。
3. 验证系统输出与后续市场方向是否具有可观测的一致性。

## 历史极值初始化

系统会优先读取 [analysis/history_bounds.py](../analysis/history_bounds.py) 中保存的 `history_bounds.json`。
如果文件不存在，会自动执行“前 7 天逐日初始分取极值”的 bootstrap：

1. 收集前 7 天视频（不含当天）。
2. 每天将当天视频的初始分取均值，得到 7 个日初始分。
3. 7 个日初始分的极小值/极大值即 `hist_min/hist_max`。

边界保存位置：

- `analysis_video/storage/analysis/history_bounds.json`

bootstrap 命令：

```bash
python analysis_video/evaluation/bootstrap_history_bounds.py
```

## 主要指标

主指标建议使用 `7日方向命中率`。

定义：

$$
\text{7日方向命中率} = \frac{\text{预测方向与 7 日后真实方向一致的样本数}}{\text{有效标注样本数}}
$$

方向映射规则：

- `加仓/持有`、`重点关注/择机买入` 视为 `up`
- `卖出/规避`、`减仓/观望` 视为 `down`
- `持有/观望` 视为 `flat`

为什么这个指标有意义：

- 它直接衡量系统是否能给出与后续市场走势一致的判断。
- 比单纯的“有输出”更强，能说明系统不是只会生成文本，而是真的有方向性信息。
- 这个指标可按周持续跟踪，适合论文和实验章节展示趋势。

## 评估流程

1. 准备标签文件 `evaluation/data/directional_labels_template.csv`。
2. 运行评估脚本。
3. 查看输出的 `directional_hit_rate_report.json`。

评估命令：

```bash
python analysis_video/evaluation/evaluate_directional_hit_rate.py --labels analysis_video/evaluation/data/directional_labels_template.csv
```

输出目录：

- `analysis_video/evaluation/reports/`
