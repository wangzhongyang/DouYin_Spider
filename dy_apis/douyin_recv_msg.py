import hashlib
import json
import threading
import time

from websocket import ABNF, WebSocketApp

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
    # 心跳：空闲连接会被中间设备（NAT/代理）静默丢弃而不发 FIN，
    # 20 秒一次 ping、10 秒内收不到 pong 就判定断线重连。
    PING_INTERVAL = 20
    PING_TIMEOUT = 10
    # 应用层心跳：PC Web 实录每 30 秒发一个 PushFrame{service=9999, method=1,
    # payloadType="hb"}，seqId/logId 自增。不发的话服务端会在 TCP 不断的情况下
    # 静默作废推送订阅（2026-11-27 实测：18:41 后 socket 仍是 ESTABLISHED 但没有推送）。
    HEARTBEAT_INTERVAL = 30

    def __init__(self, auth: DouyinAuth, auto_reconnect=True, on_event=None):
        self.auto_reconnect = auto_reconnect
        # 可选的结构化回调：MCP 服务用它把私信投进内存缓冲；CLI 不传，行为不变
        self.on_event = on_event
        self.received = 0
        self.auth = auth
        self.ws = None
        self._stopped = False            # stop() 置位，用来跳出重连循环
        self._opened = False             # 当前连接是否打开（im_listen_status 的 connected 用它）
        self._ever_opened = False        # 本轮是否连上过（用来重置退避）
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
        self._ever_opened = True
        print("WebSocket connection open.")
        self._start_heartbeat()

    def _start_heartbeat(self):
        """每 HEARTBEAT_INTERVAL 秒发一个 hb 帧，和 PC Web 客户端一致。"""
        self._stop_heartbeat()
        self._hb_stop = threading.Event()
        self._hb_seq = 0
        stop = self._hb_stop

        def loop():
            while not stop.wait(self.HEARTBEAT_INTERVAL):
                ws = self.ws
                if ws is None or not self._opened:
                    continue
                self._hb_seq += 1
                frame = Live_pb2.PushFrame(
                    seqId=self._hb_seq, logId=self._hb_seq,
                    service=9999, method=1, payloadType='hb',
                )
                try:
                    ws.send(frame.SerializeToString(), ABNF.OPCODE_BINARY)
                except Exception:
                    return  # 连接没了，交给 start() 的重连循环

        self._hb_thread = threading.Thread(target=loop, name="douyin-im-hb", daemon=True)
        self._hb_thread.start()

    def _stop_heartbeat(self):
        ev = getattr(self, "_hb_stop", None)
        if ev is not None:
            ev.set()
            self._hb_stop = None

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
        # 这里只记录。是否重连统一由 start() 的循环判断：以前只有在
        # ConnectionRefusedError / ConnectionClosedException 上打标记才重连，
        # 其它错误（包括服务端正常 close 帧，on_error 根本不触发）会让
        # run_forever 返回后循环直接退出，监听线程静默死掉、不再收消息。

    def on_close(self, ws, close_status_code, close_msg):
        self._opened = False
        self._stop_heartbeat()
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
        """阻塞运行；断线按退避重连，直到 stop() 或 auto_reconnect=False。

        重连是**循环**，不是递归压栈。判断依据只看“是否被主动停止”，
        不再依赖具体异常类型：服务端正常 close（on_error 不触发）同样要重连。

        连接期间：WS 心跳（PING_INTERVAL/PING_TIMEOUT）探活 + 应用层 hb 帧
        （HEARTBEAT_INTERVAL）维持服务端推送订阅。
        """
        backoff = self.RECONNECT_BACKOFF_START
        while not self._stopped and self.auto_reconnect:
            self._ever_opened = False
            self.ws = self._new_ws()
            try:
                self.ws.run_forever(
                    origin='https://www.douyin.com',
                    ping_interval=self.PING_INTERVAL,
                    ping_timeout=self.PING_TIMEOUT,
                )
            except KeyboardInterrupt:
                try:
                    self.ws.close()
                except Exception:
                    pass
                break
            except Exception as e:
                print(f"\033[31m### run_forever 异常: {type(e).__name__}: {e} ###\033[m")
                try:
                    self.ws.close()
                except Exception:
                    pass
            if self._stopped or not self.auto_reconnect:
                break
            if self._ever_opened:
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
