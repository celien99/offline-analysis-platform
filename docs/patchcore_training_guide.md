# PatchCore 模型训练操作指南

## 概述

PatchCore 是 seat_defect_core 中的纹理异常检测模块。训练流程：用冻结 CNN 提取正常样本特征 → Coreset 压缩构建 memory bank → FAISS 建索引 → 用 image-level score 分布确定阈值 → 导出 .npz 模型文件。

## 环境准备

### 1. 复制训练代码到 Windows

将以下目录从 Mac/Linux 复制到 Windows 训练机器：

```
seat_defect_core/          ← 核心训练代码
  patchcore/               ← PatchCore 引擎
  training/                ← 训练逻辑
  config.py                ← 配置模型
  config_file.py           ← 配置文件解析
  runtime_config_parsers.py
  util.py
  runtime_config.py
  pyproject.toml           ← 依赖声明
scripts/
  train_patchcore.py       ← 独立训练脚本
```

### 2. 安装 Python 3.11+

- 下载 [Python 3.11+](https://www.python.org/downloads/) 安装包
- 安装时勾选 "Add Python to PATH"
- 验证：`python --version` 应输出 `Python 3.11.x`

### 3. 安装依赖

在 `seat_defect_core/` 同级目录执行：

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖（PyTorch 需根据 GPU 选择 CUDA 版本）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install faiss-cpu opencv-python numpy ultralytics requests

# 或者用 uv（推荐，更快）
pip install uv
cd seat_defect_core
uv sync
```

**GPU 说明：** 如果训练机有 NVIDIA GPU，`pip install torch` 会默认安装 CUDA 版本。训练时配置 `backbone_device: "cuda"` 即可使用 GPU 加速特征提取。如果没有 GPU，配置 `backbone_device: "cpu"`。

## 准备训练数据

### 目录结构

```
data/
├── cam_front/             ← 每个机位一个子目录
│   ├── img_001.jpg        ← 正常（无缺陷）样本
│   ├── img_002.jpg
│   └── ...
├── cam_back/
│   ├── img_001.jpg
│   └── ...
└── cam_left/
    └── ...
```

### 样本要求

| 项目 | 要求 |
|------|------|
| 格式 | JPG / PNG / BMP |
| `online` 模式内容 | 正常（无缺陷）的原始相机图像，由训练脚本复用线上 YOLO → ROI → mask 流程 |
| `roi` 模式内容 | 已裁剪并标准化的正常座椅 ROI 区域图像，仅用于兼容历史训练数据 |
| 数量 | 建议 50-200 张，覆盖正常制造波动 |
| 光照 | 覆盖产线典型光照条件 |
| 拍摄 | 与线上推理使用相同的机位和角度 |

> 生产训练推荐使用 `--input-mode online`。该模式会按检测配置中的 YOLO、ROI、mask erode、edge ignore 和 region 切分逻辑准备 PatchCore 输入，避免训练样本与线上推理样本分布不一致。

## 创建训练配置

复制 `seat_defect_core/config.training.example.json` 并修改：

```jsonc
{
  "seat_defect_inspection": {
    "cameras": [
      {
        "camera_id": "cam_front",          // 机位 ID，与线上配置一致
        "patchcore": {
          "backend": "full",                // 固定为 "full"，使用 CNN 特征
          "backbone_name": "wide_resnet50_2", // 骨干网络
          "feature_layers": ["layer2", "layer3"], // 特征层
          "backbone_pretrained": true,      // 必须为 true
          "backbone_device": "cuda",        // cuda / cpu
          "image_size": 256,                // 输入尺寸
          "patch_size": 32,                 // patch 大小
          "stride": 16,                     // 步长
          "max_memory": 1024,               // memory bank 最大条目数
          "coreset_sampling_ratio": 0.1,    // Coreset 采样比例
          "threshold_quantile": 0.99,       // 阈值分位数
          "training_threshold_upper_quantile": 0.995, // 鲁棒上界
          "texture_input": "lab_l"          // 纹理通道
        }
      }
    ]
  }
}
```

**关键参数说明：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `backbone_name` | `wide_resnet50_2` | 可选 `resnet18` / `resnet50` |
| `backbone_device` | `cpu` | Windows 上修改为 `cuda`(NVIDIA GPU) 或 `cpu` |
| `max_memory` | `1024` | 正常样本多时可增大到 2048-4096 |
| `threshold_quantile` | `0.99` | 值越高阈值越严格（误报越少，漏检越多） |
| `image_size` | `256` | 与线上推理保持一致 |
| `coreset_sampling_ratio` | `0.1` | Coreset 压缩率，0 表示自动计算 |

## 执行训练

### 单机位训练（生产推荐：online 模式）

```bash
cd <项目根目录>

python scripts/train_patchcore.py \
  --config config.training.json \
  --camera-id cam_front \
  --good-images ./data/cam_front/ \
  --output ./models/cam_front_patchcore.npz \
  --input-mode online
```

`online` 模式要求配置中存在该相机的 YOLO 分割模型路径。训练脚本会跳过无法检测到座椅、缺少 mask、ROI 为空或质量门控不通过的样本，并在输出 JSON 的 `skipped_by_reason` 中给出统计。

### 局部区域 PatchCore 训练

当线上配置使用 `upper` / `middle` / `lower` 等局部区域模型时，应对每个区域分别训练：

```bash
python scripts/train_patchcore.py \
  --config config.training.json \
  --camera-id cam_front \
  --good-images ./data/cam_front/ \
  --output ./models/cam_front_upper_patchcore.npz \
  --input-mode online \
  --region-id upper
```

### 已裁 ROI 兼容训练

如果训练目录已经是历史流程导出的标准 ROI 图，可保留默认 `roi` 模式：

```bash
python scripts/train_patchcore.py \
  --config config.training.json \
  --camera-id cam_front \
  --good-images ./data/cam_front_roi/ \
  --output ./models/cam_front_patchcore.npz
```

### 批量训练多机位

```bash
python scripts/train_patchcore.py \
  --config config.training.json \
  --camera-ids cam_front,cam_back,cam_left \
  --good-images-root ./data/ \
  --output-dir ./models/ \
  --input-mode online
```

批量模式会为每个 `--camera-ids` 中的机位，从 `<good-images-root>/<camera_id>/` 读取样本，输出到 `<output-dir>/<camera_id>_patchcore.npz`。

### 训练输出

成功后会打印：

```json
{
  "memory_bank_size": 256,
  "total_embeddings": 5120,
  "threshold": 24.835,
  "artifact_path": "./models/cam_front_patchcore.npz",
  "input_mode": "online",
  "region_id": null,
  "skipped_by_reason": {
    "target_not_found": 2
  }
}
```

- `memory_bank_size`：Coreset 压缩后的 memory bank 条目数
- `total_embeddings`：所有图像的 patch embedding 总数
- `threshold`：image-level 异常分数阈值
- `artifact_path`：模型文件路径
- `skipped_by_reason`：online 模式下被跳过样本的原因统计

### 也可用原始 CLI

```bash
cd seat_defect_core
python -m seat_defect_core train-patchcore \
  --config config.training.json \
  --camera-id cam_front \
  --good-images ../data/cam_front/ \
  --output ../models/cam_front_patchcore.npz \
  --input-mode online
```

## 模型部署到线上

训练生成的 `.npz` 文件包含：

| 字段 | 说明 |
|------|------|
| `memory_bank` | Coreset 压缩后的特征库 (n, d) |
| `feature_mean` | 特征归一化均值 |
| `feature_std` | 特征归一化标准差 |
| `faiss_index` | FAISS 搜索索引（加速推理） |
| `meta_json` | 模型超参数 JSON |

部署步骤：

1. 将 `.npz` 文件复制到线上 `seat_defect_core` 的 models 目录
2. 更新线上 `config.json` 中对应机位的 `patchcore_model_path` 指向新模型
3. 重启线上检测服务

## 常见问题

### Q: 训练报错 "torch is not available"

PyTorch 未安装或安装不正确。确认：
```bash
python -c "import torch; print(torch.__version__)"
```

### Q: 训练报错 "未能从参考图像中提取到有效 embedding"

正常样本可能不满足 min_target_coverage（默认 0.8）要求。样本需要是裁剪后的 ROI 区域（非完整座椅图），或者将 `min_target_coverage` 调低。

如果使用 `--input-mode online`，还需要检查：

- YOLO `model_path` 是否存在且能分割 `target_class`。
- `skipped_by_reason` 中是否大量出现 `target_not_found`、`target_mask_missing` 或 `quality_*`。
- `--region-id` 是否与配置里的局部区域 ID 一致。

### Q: Windows 上 faiss-cpu 安装失败

faiss-cpu 1.8+ 提供 Windows wheel 包。如果 pip 安装失败，尝试指定版本：
```bash
pip install faiss-cpu==1.8.0
```

### Q: 模型文件多大

宽 ResNet50 + layer2/layer3 → embedding dim ≈ 1792。max_memory=1024 时 memory_bank 约 7MB，加上 FAISS 索引约 7.3MB，完整 .npz 约 15MB。

### Q: 训练耗时

RTX 3060，100 张 256×256 图像：特征提取约 30 秒，FAISS 索引构建 < 1 秒，总计约 30 秒。

### Q: 如何调整阈值松紧

- 降低 `threshold_quantile`（如 0.95）→ 阈值更低 → 更松（漏检更少，误报可能变多）
- 提高 `threshold_quantile`（如 0.995）→ 阈值更高 → 更严（误报更少，漏检可能变多）
