# analysis_video

## 当前推荐入口

直接运行下面命令，即可完成一次完整流程：

- 读取博主列表
- 抓取近 24 小时视频
- 分析视频并输出情绪分与投资建议

```bash
python analysis_video/run_24h_analysis.py
```

输出会落盘到：

- `analysis_video/storage/analysis/latest_investment_report.json`

## 历史极值策略

历史极值按“前 7 天逐日初始分”生成：

1. 收集前 7 天样本（按视频 create_time 所在日期归档）。
2. 每天把当天视频计算成一个初始分（当天均值）。
3. 得到 7 个日初始分后，取极大值和极小值作为历史极值。

边界文件：

- `analysis_video/storage/analysis/history_bounds.json`

单独计算一次历史极值：

```bash
python analysis_video/compute_history_bounds_once.py
```

运行后会直接提示需要填写到 `analysis_video/analysis/config.py` 的 `HIST_MIN/HIST_MAX`。

## 可选参数

- `--skip-fetch`：跳过抓取，只分析现有 CSV。
- `--refresh-bounds`：本次运行前强制刷新历史极值（默认不刷新）。
