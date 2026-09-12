# Newsup 主实验：跨领域真实一维时间序列选型

## 统一规则

- 8 个规模档位分别来自 8 个领域、8 个发布机构或数据平台，不复用同一原始数据集。
- 全部使用真实观测，不复制、不插值扩容、不生成随机值、不补零凑大小。
- 每条序列只有一个数值通道；含多个对象的数据集保存为“多条单变量序列”，并单独保存边界索引。
- 为排除数据类型造成的存储差异，主数据统一转换为 little-endian `float64`。达到目标观测数后停止，因此文件可以做到与目标大小一致。
- 缺失值直接剔除并记录剔除数量；不使用插值填补。

## 推荐的 8 个数据集

| 目标大小 | 领域 | 数据集与发布方 | 使用的一维变量 | 所需观测数 |
|---:|---|---|---|---:|
| 64 MiB | 金融市场 | Binance BTC/USDT Spot Trades | 每笔成交价格 `price` | 8,388,608 |
| 256 MiB | 语音音频 | OpenSLR LibriSpeech | 语音波形振幅 | 33,554,432 |
| 384 MiB | 生理信号 | PhysioNet Sleep-EDF Expanded | 单通道 EEG `Fpz-Cz` | 50,331,648 |
| 512 MiB | 气象 | NOAA/NCEI Global Hourly ISD | 地面气温 | 67,108,864 |
| 640 MiB | 城市交通 | NYC TLC High Volume FHV Trips | 单次行程时长 | 83,886,080 |
| 768 MiB | 互联网访问 | Wikimedia Pageviews Dumps | 页面每小时访问次数 | 100,663,296 |
| 896 MiB | 天文观测 | NASA/MAST Kepler Light Curves | `PDCSAP_FLUX` 光通量 | 117,440,512 |
| 1 GiB | 引力波物理 | GWOSC LIGO Open Data | H1 探测器 strain | 134,217,728 |

## 来源与构造方法

### 1. 64 MiB：金融逐笔成交价格

- 官方来源：<https://data.binance.vision/?prefix=data/spot/monthly/trades/BTCUSDT/>
- 格式说明：<https://github.com/binance/binance-public-data/blob/master/README.md>
- 按月份和成交顺序读取 BTC/USDT 现货 trades，只取 `price`。
- 收集 8,388,608 个真实成交价后停止。

### 2. 256 MiB：真实语音波形

- 官方来源：<https://www.openslr.org/12/>
- 数据集为约 1,000 小时的真实朗读语音，许可为 CC BY 4.0。
- 按 LibriSpeech 的固定目录顺序读取 FLAC，解码后只取单声道振幅。
- 每个音频文件仍是一条独立单变量序列，边界写入索引文件；累计 33,554,432 个采样点后停止。

### 3. 384 MiB：睡眠 EEG

- 官方来源：<https://physionet.org/content/sleep-edfx/1.0.0/>
- PhysioNet 标明未压缩数据总量为 8.1 GB，足以构建本档。
- 依次读取 EDF 文件，仅保留 `EEG Fpz-Cz` 通道及有效样本。
- 以每个受试者、每次记录为独立序列，累计 50,331,648 个采样点。

### 4. 512 MiB：全球地面气温

- 官方来源：<https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database>
- NOAA/NCEI 的 ISD 是真实全球逐小时与天气时次观测，历史未压缩数据约 600 GB。
- 按 `station_id, timestamp` 排序，只取通过质量控制且非缺失的气温。
- 每个气象站是一条独立单变量序列，累计 67,108,864 个观测值。

### 5. 640 MiB：纽约网约车行程时长

- 官方来源：<https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>
- 使用 High Volume For-Hire Vehicle Trip Records，而不是规模较小的绿色出租车数据。
- 计算 `dropoff_datetime - pickup_datetime`，这是由两次真实记录时间确定的行程时长，不是合成数据。
- 按上车时间排序，剔除时间倒置或缺失记录，累计 83,886,080 个行程时长。

### 6. 768 MiB：Wikimedia 页面访问量

- 官方来源：<https://dumps.wikimedia.org/other/pageviews/>
- 官方说明：<https://dumps.wikimedia.org/other/pageviews/readme.html>
- 每个页面标题对应一条单变量小时访问量序列；页面之间使用边界索引分隔。
- 按 `project, page_title, hour` 的确定顺序写入真实访问次数，累计 100,663,296 个观测值。

### 7. 896 MiB：Kepler 恒星光变曲线

- 官方来源：<https://archive.stsci.edu/missions-and-data/kepler/kepler-bulk-downloads>
- 使用 NASA/MAST 发布的 Kepler Light Curves，只提取质量标志合格且非空的 `PDCSAP_FLUX`。
- 每个 KIC 天体是一条独立单变量光变曲线，按 `KIC ID, TIME` 排序。
- 累计 117,440,512 个真实光通量观测值。

### 8. 1 GiB：LIGO 引力波应变

- 官方来源：<https://gwosc.org/api/>
- 数据说明：<https://www.ligo.caltech.edu/page/ligo-data>
- 使用 GWOSC 发布的 H1 探测器、4,096 Hz strain，只选择官方数据质量标记有效的区段。
- 134,217,728 个采样点约对应 9.10 小时的有效观测；如果连续区段之间有缺口，则保留区段边界，不跨缺口伪装连续。

## 文件组织建议

每一档保存两个文件：

```text
dataset_064MiB.f64       # 只含 float64 观测值
dataset_064MiB.index.csv # 每条序列的来源标识、起始偏移、长度和时间范围
```

`.f64` 文件大小用于 Newsup 的长度实验；`.index.csv` 不计入实验输入大小，只用于追溯来源和恢复序列边界。

## 实验解释注意事项

这套设计满足“规模增加时领域也变化”的要求，但数据大小与数据领域同时变化。因此，结果适合表述为 Newsup 在不同真实领域和不同数据规模下的综合表现，不能把性能差异全部归因于数据长度。若论文还需要严格分析长度效应，应另设一个固定领域的消融实验。
