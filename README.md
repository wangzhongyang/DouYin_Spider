<div align="center">
  <p align="center">
    <a href="https://github.com/cv-cat/Douyin_Spider" target="_blank" align="center" alt="Go to Douyin_Spider Website">
      <picture>
        <img width="220" src="./author/logo.jpg" alt="Douyin_Spider logo">
      </picture>
    </a>
  </p>
  <div align="center">
      <a href="https://www.python.org/">
          <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python 3.9+">
      </a>
      <a href="https://nodejs.org/zh-cn/">
          <img src="https://img.shields.io/badge/nodejs-18%2B%20(optional)-lightgrey" alt="NodeJS 18+ (optional)">
      </a>
  </div>
  
  # 🎶DouYin_Spider
  
</div>


## ❤️Sponsor

<div align="center">

<a href="https://api.openai-next.com">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./author/sponsors/vectrust-dark.png">
    <img src="./author/sponsors/vectrust.png" alt="Vectrust" height="72">
  </picture>
</a>

**Sponsored by [Vectrust](https://api.openai-next.com) @ OpenDev Org & NextRouter Alliance**

<sub>[想出现在这里？](mailto:992822653@qq.com)</sub>

</div>

---

<div align="center">

[![FastAIToken](https://raw.githubusercontent.com/TheSmallHanCat/flow2api/main/static/sponsors/fastaitoken-banner.png)](https://www.fastaitoken.com/register?aff=48J4VXUABAAV)

</div>

**FastAIToken** 是面向开发者的 AI API 聚合平台，支持 OpenAI、Claude、Gemini 等主流大模型，兼容 OpenAI API 协议，可无缝接入 **Claude Code、Codex、Gemini CLI、Cherry Studio、Cline、Continue** 等各类 AI 开发工具。平台采用 **充值 1:1（1 元 = 1 美元 API 额度）**，帮助开发者以更低成本、更高效率地使用全球领先的大模型服务。

平台提供多个可选分组与公开状态页，开发者可根据成本、响应速度和稳定性自由选择不同渠道，并享受 **7×24 小时真人技术支持**（非机器人）。

**主要做 AI 开发接入？可以试试 [FastAIToken](https://www.fastaitoken.com/register?aff=48J4VXUABAAV)，兼容 Codex / Claude Code / Gemini CLI 等主流工具。**

---

**✨ 专业的抖音数据采集与交互解决方案，支持数据爬取、直播间监听、私信收发、创作者发布等功能**

大模型时代，自动化是每个开发者都绕不开的课题。
当你想让 AI Agent 真正落地到抖音——自动处理私信、感知直播间动态、驱动内容互动——第一道墙往往不是模型能力，而是**平台通信能力的缺失**。

本项目做的事很简单：把这道墙拆掉。

**⚠️ 严禁用于发布不良信息、违法内容！本项目仅供学习与技术研究使用，如有侵权请联系作者删除，后果自负。**

## 🌟 功能特性

- ✅ **多维度数据采集**
  - 用户主页信息 / 作品详情
  - 评论区数据（含多级回复）
  - 智能搜索（视频 / 用户 / 直播）
  - 关注 / 粉丝列表
  - 消息通知 / 收藏列表 / 推荐流
- 🎙️ **直播间实时监听**
  - 弹幕消息 / 礼物（含送礼对象）/ 进场 / 关注 / 点赞 / 房间热度
  - PK 实时事件 / PK 排行榜 / 直播间贡献榜
  - 直播间发送弹幕消息
  - 直播间点赞
- 💬 **抖音私信收发**
  - WebSocket 实时接收私信（文本 / 表情包 / 语音 / 图片 / 分享视频）
  - 主动发送私信
  - 创建 / 查询会话列表
- 🤝 **互动操作**
  - 点赞视频
  - 发布评论 / 回复评论
  - 收藏 / 移动 / 取消收藏作品
- 📤 **创作者中心**
  - 发布图集 / 视频（支持可见范围、是否允许下载等设置）
- 🔑 **多种登录方式**
  - Cookie / 扫码登录 / 手机号验证码登录
- 🚀 **高性能架构**
  - 自动重试机制 / 断线重连
- 🔒 **安全稳定**
  - 抖音最新 API 适配
  - 异常处理机制
  - proxy 代理
- 🎨 **便捷管理**
  - 结构化目录存储
  - 格式化输出（JSON / EXCEL / MEDIA）

## 🎨效果图
### 处理后的所有用户
![image](https://github.com/cv-cat/DouYin_Spider/assets/94289429/3f3ff858-c443-4a68-bae6-1d16ef43011d)
### 某个用户所有的视频\图集
![image](https://github.com/cv-cat/DouYin_Spider/assets/94289429/fa6f5e65-7e3c-4abf-b140-cd20c33d3b43)
### 某个视频\图集具体的内容
![image](https://github.com/cv-cat/DouYin_Spider/assets/94289429/16cfc027-6186-4914-bca4-901f886a9b82)
### 某个直播时的具体弹幕发言和礼物数据
![image](https://github.com/cv-cat/DouYin_Spider/assets/94289429/e2cde1f1-6309-44fe-8aa3-bca2821bf30d)
### 保存的excel
![image](https://github.com/user-attachments/assets/5dfd8fb4-7597-4f54-af6a-9ab8ba766b7c)



## 🛠️ 快速开始
### ⛳运行环境
- Python 3.9+
- Node.js 18+（可选，仅部分直播 / 验证码场景会调用，主流程签名已全部纯 Python 实现）

### 🎯安装依赖
```
pip install -r requirements.txt
```

### 🎨配置文件

现在推荐只配置 `DY_COOKIES`：主站 `Auth` 会被作品接口、直播 REST/WebSocket 和创作者中心共同复用。
`DY_LIVE_COOKIES` 仍可作为旧版独立直播浏览器的显式覆盖，但不再是必填项。

配置文件在项目根目录.env文件中，将下图自己的登录cookie放入其中，cookie获取➡️在浏览器f12打开控制台，点击网络，点击fetch，找一个接口点开
![image](https://github.com/user-attachments/assets/6a7e4ecb-0432-4581-890a-577e0eae463d)

复制cookie到.env文件中（注意！登录抖音后的cookie才是有效的，不登陆没有用）
![image](https://github.com/user-attachments/assets/60291f3f-9b69-423f-8b11-167278d44639)

> ⚠️ 请在 `www.douyin.com` 登录后，从任意 `/aweme/v1/web/` 接口请求中复制**完整** cookie，确认其中包含 `UIFID` 字段。缺少 `UIFID` 时作品详情、搜索等接口会被风控拦截（`Uifid Not Found`）。

> `UIFID` 是推荐流接口响应下发的设备标识，复制完整 Cookie 后会自动带上，用户不需要手工生成或填写。

### 写接口的 dtrait 配置

发布、评论、点赞、收藏等写接口会发送按请求路径重算的 `x-tt-session-dtrait`。项目默认加载随包的 [utils/dtrait_profile.json](utils/dtrait_profile.json)，通常不需要额外配置；显式设置 `DY_DTRAIT_BLOB` 时会优先使用它。

`utils/dtrait_features.py` 是 dtrait 内层 VM 的纯 Python 实现，负责 Murmur3、特征标签、布尔位图和 base64 打包；档案里的渲染哈希是设备一次采样后复用的常量，外层 RSA/AES 则每次按请求路径和时间重新计算。

换设备时可以在 `.env` 中设置 `DY_DTRAIT_PROFILE` 指向自己的设备档案 JSON。抓取时在已登录的 `www.douyin.com` 打开开发者工具，在 Console 先执行下面的 hook，再回到页面触发一次点赞、收藏或评论请求：

```js
(() => {
  const aes = window.DTraitUcAesEncrypt;
  if (!aes?.encryptData) throw new Error('dtrait SDK 尚未初始化，请先刷新并等待页面加载完成');
  const original = aes.encryptData;
  aes.encryptData = function (...args) {
    for (const value of args) {
      const text = typeof value === 'string' ? value : JSON.stringify(value ?? '');
      try {
        const payload = JSON.parse(text);
        if (payload?.dtrait) console.log('DY_DTRAIT_BLOB=', payload.dtrait);
      } catch (_) {}
    }
    return original.apply(this, args);
  };
  console.log('dtrait hook installed; now trigger one write request');
})();
```

把 Console 打印的 `DY_DTRAIT_BLOB` 值复制到 `.env`。不要复制完整 Cookie 或 `x-tt-session-dtrait` 外层密文；外层头会由项目按当前路径和时间重新生成。



### 🚀运行项目
```
# 数据爬取
python main.py

# 直播间监听（弹幕 / 礼物 / 点赞等）
python -m dy_live.server <LIVE_ID>

# 抖音私信实时接收
python dy_apis/douyin_recv_msg.py

# 创作者中心快速发布图集 / 视频（先修改文件顶部的“用户配置”）
python quick_publish.py

# 远程 MCP 服务（OAuth 2.0 登录，对外暴露所有能力）
python -m mcp_server
```

### 🧩 MCP 服务（远程 / OAuth 2.0 / Cloudflare 隧道）

把上面这些能力原样包装成 MCP 工具，给 Claude Desktop / Cursor / ChatGPT 之类的客户端用。
**不改动任何已有入口**——这是纯新增的一层 HTTP + 鉴权 + 工具声明，抖音协议、签名、登录态、
发布链路全部复用 `dy_apis` / `utils` 里的现有实现。

#### 安装与启动

```bash
# MCP 依赖独立成一档，爬虫本体不需要装
pip install -r requirements-mcp.txt      # mcp>=1.30,<2
conda activate DouYin_Spider             # 项目事实上的运行环境（Python 3.10）

python -m mcp_server --check             # 先看配置与工具清单（不起服务）
python -m mcp_server                     # 起服务，默认 127.0.0.1:8765
```

#### `.env` 里新增的配置

```dotenv
MCP_HOST=127.0.0.1
MCP_PORT=8765
MCP_PUBLIC_URL=https://douyin.vbvcv.xyz   # 必须与隧道 ingress 的 hostname 一致
MCP_USERNAME=douyin                       # 登录页账号
MCP_PASSWORD=change-me                    # 登录页密码，务必改成自己的
MCP_ENABLE_WRITE=on                       # off = 只注册只读工具
MCP_WRITE_RATE_LIMIT=300                  # 写接口滑动窗口（次）
MCP_WRITE_RATE_WINDOW=600                 # 窗口秒数
MCP_LOGIN_MAX_FAILS=5                     # 同 IP 失败几次后锁定
MCP_LOGIN_LOCK_SECONDS=300
```

`MCP_SECRET_KEY` 留空会自动生成到 `datas/mcp/secret.key`（0600），用于给
`/login?req=…` 链接签名；OAuth 状态存在 `datas/mcp/oauth.db`（SQLite，已 gitignore）。

#### 对外端点

| 路径 | 说明 |
|---|---|
| `POST /mcp` | MCP 端点（Streamable HTTP），需 `Authorization: Bearer <access_token>` |
| `GET /authorize` | 授权入口，校验 client / redirect_uri / PKCE 后跳到登录页 |
| `GET POST /login` | 用户名密码登录页（就是 `MCP_USERNAME` / `MCP_PASSWORD`） |
| `POST /token` | 授权码换 token / refresh 换 token |
| `POST /register` | 动态客户端注册（DCR，RFC 7591） |
| `POST /revoke` | 撤销令牌 |
| `GET /.well-known/oauth-authorization-server` | AS 元数据（RFC 8414） |
| `GET /.well-known/oauth-protected-resource/mcp` | 受保护资源元数据（RFC 9728） |
| `GET /healthz` | 免认证探活：版本 / 工具数 / issuer |

#### 客户端怎么接

浏览器类客户端（Claude Desktop / ChatGPT 连接器）：新建自定义连接器，URL 填
`https://douyin.vbvcv.xyz/mcp`，点连接后会自动打开登录页，输 `MCP_USERNAME` /
`MCP_PASSWORD` 即可，令牌自动保存并刷新。

配置文件类客户端（Cursor / Claude Code / Cline 等）：

```json
{
  "mcpServers": {
    "douyin": {
      "type": "http",
      "url": "https://douyin.vbvcv.xyz/mcp"
    }
  }
}
```

不做 DCR 的客户端可以预注册：`.env` 里填 `MCP_CLIENT_ID` / `MCP_CLIENT_SECRET` /
`MCP_CLIENT_REDIRECT_URIS`（逗号分隔）。

#### 私信接收（WebSocket 推送）

抖音**没有私信历史接口**，能拿到的只有 WebSocket 推送。所以 MCP 侧是一套
「常驻连接 + 内存环形缓冲 + 按 seq 增量取」的模型：

| 工具 | 作用 |
|---|---|
| `im_listen_status` | 看是否在连、连上没有、缓冲多少条、丢了多少 |
| `im_listen_events(after_seq, limit, wait_seconds)` | 增量取新消息；`wait_seconds` 长轮询最多 25s |
| `im_listen_start` / `im_listen_stop` | 手动启停（默认开机自动连，`MCP_IM_AUTOSTART=on`） |

每条事件含：`seq`、`type`（7 文本 / 5 表情 / 17 语音 / 27 图片 / 8 分享视频 / 50001 已读回执）、
`uid`、**`conversation_type`（1 单聊 / 2 群聊）与 `chat_type`（single / group）**、
`conversation_id`、`conversation_short_id`、`index`、`server_message_id`，
以及 `text`（文本）或 `url`（媒体地址）、`ts` / `received_at`。
表情消息（type=5）额外带 `image_id / uri / package_id / display_name`，并把服务端原始
content 放在 `raw_content`（含 `width / height / image_type / aweType` 等，转发或精确
收藏时用）。

> 群聊**现在可以收也可以发**：`im_conversations(conversation_type=2)` 拿群会话的
> `conversation_id / conversation_short_id / ticket`，再用
> `im_send_text_to_conversation(..., conversation_type=2)` 回复；ticket 留空会自动解析。
> 还可直接从 `im_listen_events` 的群消息事件里取 `conversation_id / conversation_short_id`。
> 单聊的 `im_send_*`（按用户寻址）保持原样，内部仍是 `create_conversation(conversation_type=1)`。
>
> 群消息还支持这些附加能力（单聊文本工具同样可用）：
> - **@人**：`im_conversation_members` 查成员 uid，然后
>   `mentions=[{"uid": "53127236531", "name": "young🧐"}]`；工具会补 `@昵称 `、
>   `richTextInfos`（infoType 1/2）和 `mentioned_users`。
> - **表情**：`emoji_list` 返回可用 token（如 `[微笑]`），
>   `emojis=["[微笑]"]` 直接拼进正文；表情就是文本 token，客户端按 token 渲染。
> - **表情包**：`sticker_favorites` 列收藏、`sticker_collect` 收藏/取消收藏、
>   `im_send_sticker_to_conversation` 发到群；GIF 面板表情要传 `awe_type=501`，
>   消息贴纸用默认 510，否则 PC 端会显示“暂不支持该消息类型展示”。
> - **引用回复**：`im_listen_events` 事件里的 `server_message_id` 就是引用目标，
>   `reply={"server_message_id": ..., "uid": ..., "nickname": ..., "hint": ...}`；
>   content 的 `aweType` 会切成 703（TEXT_REF_MSG），并写入 `ref_msg_info`。

客户端用法：`im_listen_events(after_seq=0)` 拿全量 → 记下 `next_seq` →
下次 `after_seq=next_seq`，或者直接 `wait_seconds=20` 长轮询等新消息。
缓冲上限由 `MCP_IM_BUFFER` 控制（默认 5000），溢出时 `dropped` 会增加；
**服务停机期间的消息补不回来**（推送模型固有限制）。

延迟参考（实测，上海→抖音，经 Cloudflare 隧道）：单次接口往返约 0.6–0.8s；
私信推送到达 WS 后进缓冲是亚秒级，`im_listen_events` 一次取数约 0.4s。

#### Scope 与写操作

- `douyin.read`：所有查询类工具（用户、作品、评论、搜索、直播榜单、私信会话信息…）
- `douyin.write`：点赞、评论（含图片表情、@ 提及 `text_extra`）、收藏、发私信、直播间点赞/弹幕、创作者发布、下载/导出

默认 DCR 会把两个 scope 都给客户端。写操作额外受 `MCP_WRITE_RATE_LIMIT`（默认 300 次 / 600 秒）限流；
`MCP_ENABLE_WRITE=off` 时写工具根本不会注册（整个服务退化成只读）。

#### Cloudflare 隧道

```bash
cloudflared tunnel create douyin           # 一次性
cloudflared tunnel route dns douyin douyin.vbvcv.xyz
cloudflared tunnel --config ~/.cloudflared/config-douyin.yaml run
```

`~/.cloudflared/config-douyin.yaml`：

```yaml
tunnel: douyin
credentials-file: /Users/<you>/.cloudflared/<uuid>.json
ingress:
  - hostname: douyin.vbvcv.xyz
    service: http://127.0.0.1:8765
  - service: http_status:404
```

#### 排障

- `401 Authentication required`：客户端没拿到 token，检查 `/mcp` 响应头里的
  `resource_metadata` 是否公网可达。
- 工具报 `Uifid Not Found` 之类：`.env` 的 `DY_COOKIES` 失效了，先调 `auth_status` 确认。
- 公网 502：本地服务没起（`lsof -iTCP:8765`），或隧道 ingress 端口写错。
- 登录页提示“授权链接已过期”：链接有效期 10 分钟，回客户端重新发起连接。


### 🗝️注意事项
- `main.py` 是爬虫入口，可根据需求自行修改调用
- `dy_apis/douyin_api.py` 包含全部 API 接口封装，含直播间点赞、发消息、私信收发等
- `dy_live/server.py` 包含直播间 WebSocket 监听逻辑
- `dy_apis/douyin_recv_msg.py` 包含抖音私信 WebSocket 实时接收逻辑
- `dy_apis/douyin_creator_api.py` 包含创作者中心上传 / 发布作品接口
- `dy_apis/login_api.py` 包含扫码、手机号验证码登录逻辑
- `dy_live/pk.py` 包含直播间 PK 事件解析
- `mcp_server/` 是远程 MCP 服务（OAuth 登录 + 工具包装）；直播**实时监听**没有做成 MCP 工具（长连接不适合请求-响应模型），仍用 `python -m dy_live.server`


## 🍥日志
   
| 日期       | 说明                                   |
| -------- | ------------------------------------ |
| 23/10/05 | - 项目完成。 |
| 23/10/17 | - 首次提交。 |
| 23/10/18 | - 监听直播间弹幕和礼物。 |
| 23/10/21 | - 新增搜索智能排序和限制时间。 |
| 23/10/21 | - 新增可视化界面到release v1.1.0。 |
| 23/10/25 | - 新增issue提出的输出直播间消息时包括用户等级。 |
| 23/10/28 | - 遇到验证码请手动点击！Fix Some Bugs。 |
| 23/11/11 | - 修复了很多很多大家的bug~~，关于v.dy格式的url正在处理 |
| 23/12/22 | - 修复了直播间监控 |
| 25/06/07 | - 开放所有之前闭源的代码，包括数据爬取和直播间监听 |
| 26/04/09 | - 修复直播间礼物信息接收（含送礼对象）；新增直播间点赞、直播间发弹幕；新增抖音私信实时接收（WebSocket）与主动发送功能 |
| 26/07/26 | - 签名算法全部改为纯 Python 实现，主流程不再依赖 Node.js；私信支持浏览器登录 |
| 26/08/30 | - 新增创作者中心发布图集 / 视频；新增扫码、手机号验证码登录 |
| 26/09/13 | - 新增直播间贡献榜接口 |
| 26/09/19 | - 新增直播间 PK 排行榜接口与 PK 实时事件监听 |
| 26/09/20 | - 对齐直播间弹幕发送与作品评论发布接口 |
| 26/09/27 | - 修复视频下载（CDN 需带 Referer，之前会把 403 页面存成 mp4）；单个作品下载失败时跳过，不再中断整批 |
| 26/11/23 | - 评论发布支持图片表情（`publish_comment` 新增 `sticker` 参数，字段对齐 PC Web 前端） |
| 26/11/24 | - 新增远程 MCP 服务：OAuth 2.0 登录 + 56 个工具 + Cloudflare 隧道（douyin.vbvcv.xyz），已有入口零改动；私信支持实时接收；评论支持 @ 提及（`text_extra`） |
| 26/11/24 | - MCP 工具补齐到 79 个：评论/搜索/粉丝/通知的游标分页、私信图集/网页/名片/任意卡片、创作者合集/热点/章节/封面参数、批量下载；修正 `visibility` 文档（1 = 仅自己可见）、`poi` 必须是对象、`douyin_api_call` 的只读标注与 `MCP_ENABLE_WRITE` 绕过问题 |
| 26/11/24 | - 私信支持群消息回复：新增会话列表（`im_conversations`，单聊/群聊分开查）、会话 ticket（`im_conversation_ticket`）、按会话发送（`im_send_text_to_conversation`，`conversation_type=2` 即群聊）；发送链路 `conversation_type` 参数化，不再写死 1 |
| 26/11/24 | - 群消息补齐 @人 / 表情 / 引用回复（工具数 84）：`im_conversation_members`（成员 uid）、`emoji_list`（表情 token）、`sticker_favorites` / `sticker_collect`（收藏表情包列表、收藏/取消收藏）、`im_send_sticker_to_conversation`（群发表情包，`awe_type` 501=GIF / 510=消息贴纸）、`im_send_text_to_conversation` 支持 `mentions` / `emojis` / `reply`；回复走 `aweType=703 + ref_msg_info`；私信 type=5 事件补充 `image_id / uri / package_id` 便于直接收藏 |

## 🤝 欢迎贡献 PR

本项目欢迎任何形式的贡献！如果你有新功能想法、Bug 修复或文档改进，欢迎提交 PR。

- Fork 本仓库并在新分支上开发
- 保持代码风格与现有代码一致
- PR 描述中请简要说明改动内容和目的
- 也欢迎通过 [Issue](https://github.com/cv-cat/DouYin_Spider/issues) 提出建议或报告问题

## 🧸额外说明
1. 感谢star⭐和follow📰！不时更新
2. 作者的联系方式在主页里，有问题可以随时联系我
3. 可以关注下作者的其他项目，欢迎 PR 和 issue
4. 感谢赞助！如果此项目对您有帮助，请作者喝一杯奶茶~~ （开心一整天😊😊）
5. thank you~~~

<div align="center">
  <img src="./author/wx_pay.png" width="400px" alt="微信赞赏码"> 
  <img src="./author/zfb_pay.jpg" width="400px" alt="支付宝收款码">
</div>


## 📈 Star 趋势

<a href="https://cvcat.site/star-history/svg?repos=cv-cat/DouYin_Spider&type=Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cvcat.site/star-history/svg?repos=cv-cat/DouYin_Spider&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://cvcat.site/star-history/svg?repos=cv-cat/DouYin_Spider&type=Date" />
    <img alt="Star History Chart" src="https://cvcat.site/star-history/svg?repos=cv-cat/DouYin_Spider&type=Date" />
  </picture>
</a>



## 🍔 交流群

如果你对爬虫和 AI Agent 感兴趣，可以加入群聊一起讨论~

ps: 请加群，人满或者过期 issue | wx 提醒 | qq提醒

| group-1 | group-2 | group-3 | group-4 (2000人qq群) |
|:--:|:--:|:--:|:--:|
| <img width="280" alt="group1" src="https://cvcat.site/assets/group1.jpg" /> | <img width="280" alt="group2" src="https://cvcat.site/assets/group2.jpg" /> | <img width="280" alt="group3" src="https://cvcat.site/assets/group3.jpg" /> | <img width="280" alt="group3" src="https://cvcat.site/assets/group4.jpg" /> |


## 发布链二次验证（2026-10-17 逆向）

`create_v2` 可能返回 `x-tt-verify-passport-decision` 要求二次验证（HTTP 200 空 body）：

- **gateway_biz_verify**：`DYLoginApi` 可发起扫码二次验证闭环——
  `get_qrcode` 参数 `aid=6383`（勿用 2906，回 4031）+ `scene=secondary_verify` +
  `verify_scene=creator`，用户抖音 App 扫码后 `check_qrconnect` status=confirmed。
- **gateway_web_authlv_check**：认证等级不足，扫码不够（需短信/人脸/密码）。
  纯 HTTP 会话发码被 error_code=16 拒——建议用 cookie 导入（同设备已信任会话）。

安全相关对齐基线（2026-10-17）：UA/sec-ch-ua Chrome 155、PASSPORT_SDK 3.4.9 族、
dtrait 与真实设备逐字节一致、Cookie 头按浏览器 wire 顺序（`DouyinAuth.BROWSER_COOKIE_ORDER`）、
creator 域 msToken 走 ms_appid=2906 独立通道。
