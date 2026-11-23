#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time : 2024/6/8 下午6:57
# @Author : crush0
# @Description :
import json
import random

import uuid

from utils.fingerprint import get_profile
import static.Request_pb2 as RequestProto
from builder.header import HeaderBuilder
from utils.dy_util import generate_req_sign, generate_millisecond


class ProtoBuilder:
    # The PC IM client rolled its protobuf envelope independently of the
    # main-site version.  These values are present on every current
    # imapi request (conversation reads as well as message sends).
    SDK_VERSION = "0.1.8"
    BUILD_NUMBER = "0d50935:feat/pc-im-groupB"

    @staticmethod
    def build_normal_request(auth, cmd):
        request = RequestProto.Request()
        request.cmd = cmd
        request.sequence_id = random.randint(10000, 11000)
        request.sdk_version = ProtoBuilder.SDK_VERSION
        # The current PC IM envelope leaves the legacy top-level auth token
        # empty.  Authentication is carried by the ticket-guard HTTP headers
        # and (for sends) the conversation ticket in the nested body.
        request.refer = 3
        request.inbox_type = 0
        request.build_number = ProtoBuilder.BUILD_NUMBER
        request.device_id = '0'
        request.device_platform = 'douyin_pc'
        request.version_code = '360000'
        request.headers['session_aid'] = '6383'
        request.headers['session_did'] = '0'
        request.headers['app_name'] = 'douyin_pc'
        request.headers['priority_region'] = 'cn'
        request.headers['user_agent'] = HeaderBuilder.ua
        request.headers['cookie_enabled'] = 'true'
        request.headers['browser_language'] = 'zh-CN'
        request.headers['browser_platform'] = 'Win32'
        # IM's protobuf client uses navigator.appName/appVersion here, unlike
        # the public REST query helpers which use the Chrome brand/version.
        # Current Chrome wire capture: browser_name="Mozilla" and
        # browser_version is UA without the leading "Mozilla/".
        request.headers['browser_name'] = 'Mozilla'
        request.headers['browser_version'] = get_profile()["ua"].replace(
            'Mozilla/', '', 1
        )
        request.headers['browser_online'] = 'true'
        request.headers['screen_width'] = get_profile()["screen_width"]
        request.headers['screen_height'] = get_profile()["screen_height"]
        # The PC IM shell is entered from the精选 page; the browser puts this
        # page referrer in the protobuf map (it is not the HTTP Referer).
        request.headers['referer'] = 'https://www.douyin.com/jingxuan'
        request.headers['timezone_name'] = 'Asia/Shanghai'
        request.headers['deviceId'] = '0'
        request.headers['is-retry'] = '0'
        request.auth_type = 4
        request.biz = 'douyin_web'
        request.access = 'web_sdk'
        # Current PC IM envelopes authenticate the HTTP request with
        # bd-ticket-guard headers.  Unlike the legacy web-protect envelope,
        # they leave the top-level ts_sign/sdk_cert fields unset; keeping them
        # here makes the body larger and no longer matches Chrome.
        return request

    @staticmethod
    def build_create_conversation_request(auth, toId, myId):
        request = ProtoBuilder.build_normal_request(auth, 609)
        request.body.create_conversation_v2_body.conversation_type = 1
        request.body.create_conversation_v2_body.participants.extend([int(toId), int(myId)])
        reuqest_sign = generate_req_sign({
            "sign_data": f"avatar_url=&idempotent_id=&name=&participants={toId},{myId}",
            "certType": "cookie",
            "scene": "web_protect"
        }, auth.private_key)
        request.reuqest_sign = reuqest_sign
        return request

    @staticmethod
    def build_get_conversation_list_info_request(auth, toId, myId, conversation_short_id):
        request = ProtoBuilder.build_normal_request(auth, 610)
        request.body.get_conversation_info_list_v2_body.data.conversation_id = f"0:1:{myId}:{toId}"
        request.body.get_conversation_info_list_v2_body.data.conversation_short_id = conversation_short_id
        request.body.get_conversation_info_list_v2_body.data.conversation_type = 1
        return request

    @staticmethod
    def build_send_message_request(auth, conversation_id, conversation_short_id, ticket,
                                   message=None, identity_security_token="",
                                   identity_security_device_id="", *,
                                   message_type=7, content=None, ext=None,
                                   mentioned_users=None, client_message_id=None,
                                   conversation_type=1, ref_msg_info=None):
        """Build a PC-IM ``message/send`` envelope.

        ``message`` is kept as the first positional argument for backwards
        compatibility with the original text-only helper.  Rich messages pass
        their JSON object through ``content`` and select the wire
        ``message_type`` explicitly.  The protobuf field itself is always a
        compact JSON string, matching the browser SDK.

        ``conversation_type`` 1 单聊 / 2 群聊：群会话必须显式传 2，并配合该会话
        自己的 ticket（见 ``DouyinAPI.get_conversation_ticket``）。
        """
        if content is None:
            content = message
        if content is None:
            content = ""
        client_message_id = str(client_message_id or uuid.uuid4())
        request = ProtoBuilder.build_normal_request(auth, 100)
        if isinstance(content, (dict, list, tuple)):
            encoded_content = json.dumps(
                content, ensure_ascii=False, separators=(',', ':')
            )
        else:
            encoded_content = str(content)
        request.body.send_message_body.conversation_id = conversation_id
        request.body.send_message_body.conversation_type = int(conversation_type)
        request.body.send_message_body.conversation_short_id = conversation_short_id
        request.body.send_message_body.content = encoded_content
        # The web client sends these extensions on every message.  Preserve
        # caller supplied values while retaining the defaults used by text.
        ext_map = dict(ext or {})
        # Keep the browser's stable default order first; custom extensions are
        # appended afterwards so adding one cannot perturb existing captures.
        defaults = {
            's:mentioned_users': ext_map.pop('s:mentioned_users', ''),
            's:client_message_id': ext_map.pop('s:client_message_id', client_message_id),
        }
        ext_map.pop('s:stime', None)
        for key, value in {**defaults, **ext_map}.items():
            request.body.send_message_body.ext.append(
                RequestProto.ExtValue(key=str(key), value=str(value))
            )
        request.body.send_message_body.ext.append(
            # PC IM uses ``<epoch-ms>.<five random digits>`` for this
            # extension (e.g. ``1788015776891.21440``), not a bare millisecond
            # integer as the legacy client did.
            RequestProto.ExtValue(
                key='s:stime',
                value=f'{generate_millisecond()}.{random.randrange(100000):05d}',
            )
        )
        if mentioned_users:
            request.body.send_message_body.mentioned_users.extend(
                int(uid) for uid in mentioned_users
            )
        request.body.send_message_body.message_type = int(message_type)
        request.body.send_message_body.ticket = ticket
        request.body.send_message_body.client_message_id = client_message_id
        if ref_msg_info:
            # 引用回复：SendMessageRequestBody.ref_msg_info（字段 11）。
            # static/Request.proto 里该消息的字段名是旧的（original_message_*），
            # 实际线上是 referenced_message_id(1) / hint(2) / root_*(3,4)。
            # 这里直接拼 wire 字节再 merge 进去，避免依赖生成代码里的错误命名。
            ref_payload = ProtoBuilder.proto_field_varint(
                1, int(ref_msg_info.get('referenced_message_id') or 0)
            )
            hint = ref_msg_info.get('hint')
            if hint:
                ref_payload += ProtoBuilder.proto_field_bytes(2, str(hint).encode('utf-8'))
            if ref_msg_info.get('root_message_id'):
                ref_payload += ProtoBuilder.proto_field_varint(
                    3, int(ref_msg_info['root_message_id'])
                )
            merged = (
                request.body.send_message_body.SerializeToString()
                + ProtoBuilder.proto_field_bytes(11, ref_payload)
            )
            request.body.send_message_body.ParseFromString(merged)
        # The current send envelope has no top-level ``reuqest_sign``.  The
        # request is authenticated by bd-ticket-guard HTTP headers; the
        # nested conversation ticket remains part of the protobuf body.
        # Since the 2026 PC IM rollout, message/send carries the short-lived
        # identity-security material in the protobuf header map.  Keep these
        # optional so conversation read/create requests remain usable when a
        # caller only needs the legacy envelope.
        if identity_security_token:
            # The web client wraps the token in a compact JSON object rather
            # than putting the bare token string on the wire.
            request.headers['identity_security_token'] = json.dumps(
                {'token': str(identity_security_token)}, separators=(',', ':')
            )
        if identity_security_device_id:
            request.headers['identity_security_device_id'] = str(identity_security_device_id)
        request.headers['identity_security_aid'] = ''
        return request

    # ---------- PC IM 会话列表 / ticket 的裸 protobuf 载荷 ----------
    # ``static/Request.proto`` 只声明了发送与建会话两类 body；会话列表
    # (get_conversation_list_body=2006) 和会话 ticket (get_ticket_body=2005)
    # 没有生成代码。这里按 wire 格式手工编码，再用 ParseFromString 塞进
    # RequestBody 的 unknown field（protobuf 运行时会原样保留并序列化）。

    @staticmethod
    def proto_varint(value: int) -> bytes:
        value = int(value)
        if value < 0:  # int64 负数按 10 字节补码编码
            value += 1 << 64
        out = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            out.append(byte | (0x80 if value else 0))
            if not value:
                return bytes(out)

    @classmethod
    def proto_field_varint(cls, number: int, value: int) -> bytes:
        return cls.proto_varint(number << 3) + cls.proto_varint(value)

    @classmethod
    def proto_field_bytes(cls, number: int, payload: bytes) -> bytes:
        payload = payload or b""
        return (
            cls.proto_varint((number << 3) | 2)
            + cls.proto_varint(len(payload))
            + payload
        )

    @classmethod
    def build_get_conversation_list_body(cls, *, cursor=0, limit=20,
                                         con_type=1, sort_type=1) -> bytes:
        """GetUserConversationListRequestBody（RequestBody 字段 2006）。

        con_type：1 单聊，2 群聊（实测同一账号两组互不包含）。
        """
        inner = (
            cls.proto_field_varint(1, sort_type)
            + cls.proto_field_varint(2, cursor)
            + cls.proto_field_varint(3, con_type)
            + cls.proto_field_varint(4, limit)
        )
        return cls.proto_field_bytes(2006, inner)

    @classmethod
    def build_get_ticket_body(cls, *, conversation_short_id, conversation_type=1,
                              to_id=0, ticket_type=1) -> bytes:
        """GetTicketRequestBody（RequestBody 字段 2005）。"""
        inner = (
            cls.proto_field_varint(1, ticket_type)
            + cls.proto_field_varint(2, conversation_type)
            + cls.proto_field_varint(4, to_id)
            + cls.proto_field_varint(5, conversation_short_id)
        )
        return cls.proto_field_bytes(2005, inner)

    @classmethod
    def build_get_conversation_participants_body(cls, *, conversation_id,
                                                 conversation_short_id,
                                                 conversation_type=1,
                                                 cursor=0, limit=100) -> bytes:
        """ConversationParticipantsListRequestBody（RequestBody 字段 605）。"""
        inner = (
            cls.proto_field_bytes(1, str(conversation_id).encode())
            + cls.proto_field_varint(2, conversation_short_id)
            + cls.proto_field_varint(3, conversation_type)
            + cls.proto_field_varint(4, cursor)
            + cls.proto_field_varint(5, limit)
        )
        return cls.proto_field_bytes(605, inner)

    @staticmethod
    def parse_proto_fields(payload: bytes) -> dict:
        """按 wire 格式解析成 ``{字段号: [值, ...]}``；wire2 的值保持 bytes。"""

        def read_varint(buf, pos):
            shift = value = 0
            while True:
                byte = buf[pos]
                pos += 1
                value |= (byte & 0x7F) << shift
                if not byte & 0x80:
                    return value, pos
                shift += 7

        fields: dict[int, list] = {}
        pos = 0
        while pos < len(payload):
            key, pos = read_varint(payload, pos)
            number, wire = key >> 3, key & 7
            if wire == 0:
                value, pos = read_varint(payload, pos)
            elif wire == 1:
                value, pos = payload[pos:pos + 8], pos + 8
            elif wire == 2:
                length, pos = read_varint(payload, pos)
                value, pos = payload[pos:pos + length], pos + length
            elif wire == 5:
                value, pos = payload[pos:pos + 4], pos + 4
            else:
                raise ValueError(f"不支持的 protobuf wire type: {wire}")
            fields.setdefault(number, []).append(value)
        return fields
