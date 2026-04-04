# 抖音视频分析工具

这是一个用于监控和分析指定抖音博主新发布视频的自动化工具。它能够自动抓取视频、提取内容、进行 LLM 分析，并将结果通过邮件发送给指定用户。

## 环境配置

### 环境依赖

首先，建议创建一个虚拟环境来管理项目依赖：

```bash
python -m venv venv
```

激活虚拟环境：

- **Windows**:
  ```bash
  venv\Scripts\activate
  ```
- **macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```

然后，安装项目所需的依赖包：

```bash
pip install -r requirements.txt
```

#### FFmpeg 安装

- **macOS**: 使用 Homebrew 安装：
  ```bash
  brew install ffmpeg
  ```

- **Windows**:
  1. 访问 [FFmpeg 官网下载页面](https://ffmpeg.org/download.html)。
  2. 下载适用于 Windows 的编译版本。
  3. 解压文件，并将 `bin` 目录的路径添加到系统的环境变量 `Path` 中。

- **Linux**: 使用包管理器安装（以 Ubuntu/Debian 为例）：
  ```bash
  sudo apt update
  sudo apt install ffmpeg
  ```

### 环境变量配置

在项目根目录下创建一个 `.env` 文件，并根据需要配置以下变量：

```env
# 抖音 API 配置
DOUYIN_AUTH_TOKEN="your_douyin_api_token"

# 方舟大模型服务配置
ARK_API_KEY="your_ark_api_key"
```

### 变量含义

- `DOUYIN_AUTH_TOKEN`: 用于访问抖音 API 的授权令牌。
- `ARK_API_KEY`: 用于访问方舟大模型服务的 API 密钥。

## 存储文件格式

项目使用 JSON 文件来存储数据，位于 `analysis_video/config/storage/` 目录下。以下是各个文件的格式说明：

### `users.json`

存储用户信息。

```json
{
  "users": {
    "\u003cusername\u003e": {
      "id": "\u003cuser_id\u003e",
      "phone": "\u003cphone_number\u003e",
      "email": "\u003cemail_address\u003e",
      "active": true,
      "balance_cents": 12345
    }
  }
}
```

- **`\u003cusername\u003e`**: 用户的唯一名称，作为字典的键。
- **`id`**: 用户的唯一标识。
- **`phone`**: 用户的手机号。
- **`email`**: 用户的邮箱地址。
- **`active`**: 用户是否处于活动状态 (`true` 或 `false`)。
- **`balance_cents`**: 用户的账户余额（以分为单位）。

### `creators.json`

存储创作者信息。

```json
{
  "creators": {
    "\u003ccreator_name\u003e": {
      "id": "\u003ccreator_id\u003e",
      "platform": "douyin",
      "display_name": "\u003cdisplay_name\u003e",
      "meta": {}
    }
  }
}
```

- **`\u003ccreator_name\u003e`**: 创作者的唯一名称，作为字典的键。
- **`id`**: 创作者在平台上的唯一标识。
- **`platform`**: 创作者所在的平台（例如 `douyin`）。
- **`display_name`**: 创作者的显示名称。
- **`meta`**: 一个用于存储额外信息的字典。

### `follows.json`

存储用户与创作者之间的关注关系。

```json
{
  "follows": [
    {
      "user_id": "\u003cuser_id\u003e",
      "creator_id": "\u003ccreator_id\u003e",
      "created_at": 1763610200,
      "notes": ""
    }
  ]
}
```

- **`user_id`**: 用户的唯一标识。
- **`creator_id`**: 创作者的唯一标识。
- **`created_at`**: 关注关系创建时的时间戳。
- **`notes`**: 备注信息。

### `progress.json`

跟踪视频的分析进度。

```json
{
  "analyzed": {
    "\u003cuser_id\u003e": {
      "\u003cvideo_id\u003e": {
        "status": "analyzed",
        "ts": 1763626375,
        "text": "...",
        "llm_cents": 10
      }
    }
  }
}
```

- **`\u003cuser_id\u003e`**: 用户的唯一标识。`__global__` 是一个特殊的键，用于存储所有用户共享的分析进度。
- **`\u003cvideo_id\u003e`**: 视频的唯一标识。
- **`status`**: 视频的分析状态（例如 `analyzed`）。
- **`ts`**: 分析完成时的时间戳。
- **`text`**: LLM 分析后的视频内容文本。
- **`llm_cents`**: 本次分析的费用（以分为单位）。


