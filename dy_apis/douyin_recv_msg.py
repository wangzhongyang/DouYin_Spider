import hashlib
import json
import time

import websocket
from websocket import WebSocketApp

from dy_apis.douyin_api import DouyinAPI
from builder.auth import DouyinAuth
from builder.header import HeaderBuilder
from builder.params import Params
from static import Live_pb2, Response_pb2


class DouyinRecvMsg:
    appKey = "e1bd35ec9db7b8d846de66ed140b1ad9"
    fpId = '9'

    # 重连退避：1 秒起，指数增长，上限 30 秒
    RECONNECT_BACKOFF_START = 1.0
    RECONNECT_BACKOFF_MAX = 30.0

    def __init__(self, auth: DouyinAuth, auto_reconnect=True, on_event=None):
        self.auto_reconnect = auto_reconnect
        # 可选的结构化回调：MCP 服务用它把私信投进内存缓冲；CLI 不传，行为不变
        self.on_event = on_event
        self.received = 0
        self.auth = auth
        self.ws = None
        self._should_reconnect = False   # on_error 打标记，真正重连在 start() 的循环里
        self._stopped = False            # stop() 置位，用来跳出重连循环
        self._opened = False             # 本轮连接是否成功建立过（用来重置退避）
        deviceId = DouyinAPI.get_device_id(auth=self.auth)
        accessKey = f'{self.fpId + self.appKey + deviceId}f8a69f1719916z'
        accessKey = hashlib.md5(accessKey.encode(encoding='UTF-8')).hexdigest()
        params = Params()
        (params
         .add_param("aid", "6383")
         .add_param("device_platform", "douyin_pc")
         .add_param("fpid", self.fpId)
         .add_param("device_id", deviceId)
         .add_param("token", self.auth.cookie["sessionid"])
         .add_param("access_key", accessKey)
         )
        self.url = f"wss://frontier-im.douyin.com/ws/v2?{params.toString()}"

    def on_open(self, ws):
        self._opened = True
        print("WebSocket connection open.")

    def _emit(self, event: dict):
        """把一条消息交给消费方；消费方抛异常不能带走连接。"""
        self.received += 1
        if self.on_event is None:
            return
        try:
            self.on_event(event)
        except Exception as exc:  # pragma: no cover - 消费方的问题不该断线
            print(f"\033[31m### on_event 回调异常: {type(exc).__name__}: {exc} ###\033[m")

    def on_message(self, ws, message):
        frame = Live_pb2.PushFrame()
        frame.ParseFromString(message)
        if frame.payloadType == 'pb':
            response = Response_pb2.Response()
            response.ParseFromString(frame.payload)
            notify = response.body.new_message_notify
            message_obj = notify.message
            sender = message_obj.sender
            content = json.loads(message_obj.content)
            msg_type = message_obj.message_type
            conversation_id = message_obj.conversation_id
            index = message_obj.index_in_conversation

            conversation_type = int(message_obj.conversation_type or 0)
            event = {
                'type': msg_type,
                'uid': int(sender or 0),
                # 1 单聊 / 2 群聊（抖音 PC IM 的取值），未知值原样保留
                'conversation_type': conversation_type,
                'chat_type': {1: 'single', 2: 'group'}.get(conversation_type, f'type_{conversation_type}'),
                'conversation_id': conversation_id,
                'conversation_short_id': int(message_obj.conversation_short_id or 0),
                'index': int(index or 0),
                'server_message_id': str(message_obj.server_message_id or ''),
                'ts': int(time.time() * 1000),
            }
            if msg_type == 7:
                event['text'] = content.get('text', '')
                print(f'【消息编号:{index}】【聊天室ID:{conversation_id}】【来自:{sender}】文本消息:{content["text"]}')
            elif msg_type == 5:
                url_info = content.get('url') or {}
                event['url'] = (url_info.get('url_list') or [''])[0]
                event['image_id'] = str(content.get('image_id') or '')
                event['uri'] = str(url_info.get('uri') or '')
                event['package_id'] = content.get('package_id') or 0
                event['display_name'] = content.get('display_name') or ''
                # 原始 content 原样透出：转发时需要 width/height/image_type/aweType 等
                event['raw_content'] = content
                print(f'【消息编号:{index}】【聊天室ID:{conversation_id}】【来自:{sender}】用户表情包消息:{event["url"]}')
            elif msg_type == 17:
                event['url'] = content['resource_url']['url_list'][0]
                print(f'【消息编号:{index}】【聊天室ID:{conversation_id}】【来自:{sender}】语音信息:{content["resource_url"]["url_list"][0]}')
            elif msg_type == 27:
                event['url'] = content['resource_url']['origin_url_list'][0]
                print(f'【消息编号:{index}】【聊天室ID:{conversation_id}】【来自:{sender}】图片信息:{content["resource_url"]["origin_url_list"][0]}')
            elif msg_type == 8:
                event['item_id'] = str(content.get('itemId', ''))
                print(f'【消息编号:{index}】【聊天室ID:{conversation_id}】【来自:{sender}】分享视频信息:视频ID{content["itemId"]}')
            elif msg_type == 50001:
                event['read_index'] = int(content.get('read_index') or 0)
                print(f'对方已读，消息标号:{content["read_index"]}')
            self._emit(event)
        elif frame.payloadType == 'text/json':
            print(json.loads(frame.payload))

    def on_error(self, ws, error):
        print("\033[31m### error ###")
        print(error)
        print("### ===error=== ###\033[m")
        # 原写法是 `A or B and self.auto_reconnect`，按优先级等于 `A or (B and ...)`，
        # 于是 ConnectionRefusedError 会绕过 auto_reconnect 开关无条件重连。
        # 另外用 type()== 判断会漏掉子类，改 isinstance。
        if not self.auto_reconnect:
            return
        if isinstance(error, (ConnectionRefusedError,
                              websocket.WebSocketConnectionClosedException)):
            # 这里只打标记。以前是直接调 self.start()，而 start() 内部是阻塞的
            # run_forever —— 每次重连都往调用栈上再压一层，不是循环，
            # 断线次数多了栈会一直涨直到 RecursionError。真正的重连交给 start()。
            self._should_reconnect = True

    def on_close(self, ws, close_status_code, close_msg):
        print("\033[31m### closed ###")
        print(f"status_code: {close_status_code}, msg: {close_msg}")
        print("### ===closed=== ###\033[m")

    def stop(self):
        """外部主动停止：关掉当前连接并让 start() 的重连循环退出。"""
        self._stopped = True
        self.auto_reconnect = False
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass

    def _new_ws(self):
        return WebSocketApp(
            url=self.url,
            header={
                'Pragma': 'no-cache',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                'User-Agent': HeaderBuilder.ua,
                'Cache-Control': 'no-cache',
                'Sec-WebSocket-Protocol': 'binary, base64, pbbp2',
                'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits'
            },
            cookie=self.auth.cookie_str,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )

    def start(self):
        """阻塞运行；断线按退避重连。重连是**循环**，不是递归压栈。"""
        backoff = self.RECONNECT_BACKOFF_START
        while not self._stopped:
            self._should_reconnect = False
            self._opened = False
            self.ws = self._new_ws()
            try:
                self.ws.run_forever(origin='https://www.douyin.com')
            except KeyboardInterrupt:
                self.ws.close()
                break
            except Exception as e:
                print(f"\033[31m### run_forever 异常: {type(e).__name__}: {e} ###\033[m")
                try:
                    self.ws.close()
                except Exception:
                    pass
            if self._stopped or not (self.auto_reconnect and self._should_reconnect):
                break
            if self._opened:
                # 这轮连上过，说明不是持续性故障，退避重置
                backoff = self.RECONNECT_BACKOFF_START
            print(f"\033[33m### {backoff:.0f} 秒后重连 ###\033[m")
            try:
                time.sleep(backoff)
            except KeyboardInterrupt:
                break
            backoff = min(backoff * 2, self.RECONNECT_BACKOFF_MAX)


if __name__ == '__main__':
    # websocket.enableTrace(True)
    web_protect_str = r''
    keys_str = r''
    cookies_str = r''
    auth_ = DouyinAuth()
    auth_.perepare_auth(cookies_str, web_protect_str, keys_str)
    douyinMsg = DouyinRecvMsg(auth_)
    douyinMsg.start()
