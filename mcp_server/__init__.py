"""抖音能力的远程 MCP 服务。

把 ``dy_apis`` / ``utils`` 里现成的接口原样包装成 MCP 工具，用 OAuth 2.0
（用户名密码登录）保护，经 Cloudflare 隧道对外提供。

已有入口（``main.py``、``python -m dy_live.server``、``douyin_recv_msg.py``、
``quick_publish.py``）完全不受影响；本包是纯新增的一层 HTTP + 鉴权 + 工具声明。
"""

__version__ = "1.0.0"
