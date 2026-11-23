import unittest
from unittest.mock import MagicMock, patch

from dy_apis.douyin_api import DouyinAPI


class _Auth:
    cookie = {'s_v_web_id': 'fp', 'UIFID': 'uifid'}
    cookie_str = 's_v_web_id=fp; UIFID=uifid'
    ticket = 'hash.ticket'
    ts_sign = 'ts.2.abc'
    client_cert = 'pub.x'
    private_key = 'key'
    dtrait_profile = 'profile.json'
    webid = 'webid'
    msToken = 'mstoken'

    def ticket_matches_session(self):
        return True

    def get_uid(self):
        return 2511699079608468


class CommentStickerFieldsTest(unittest.TestCase):
    def test_comment_list_sticker(self):
        # 评论列表返回的原始 sticker：有 animate_url，没有 animate_type/author
        sticker = {
            'id': 7694150285622509605,
            'id_str': '7694150285622509605',
            'width': 800,
            'height': 800,
            'sticker_type': 2,
            'author_sec_uid': '',
            'animate_url': {'uri': 'tos-cn-o-0812/abc', 'width': 800, 'height': 800},
            'static_url': {'uri': 'tos-cn-o-0812/abc', 'width': 800, 'height': 800},
        }
        fields = DouyinAPI._comment_sticker_fields(sticker)
        self.assertEqual(fields['sticker_id'], '7694150285622509605')
        self.assertEqual(fields['sticker_uri'], 'tos-cn-o-0812/abc')
        self.assertEqual(fields['sticker_width'], 800)
        self.assertEqual(fields['sticker_height'], 800)
        # 0 是合法值，2 必须保留
        self.assertEqual(fields['sticker_type'], 2)
        # 评论数据没有 animate_type / author，不发送猜测值
        self.assertNotIn('sticker_format', fields)
        self.assertNotIn('sticker_author_sec_uid', fields)

    def test_emoji_api_sticker_with_animate_type_and_author(self):
        sticker = {
            'id_str': '123',
            'width': 100,
            'height': 200,
            'sticker_type': 19,
            'animate_type': 'gif',
            'animate_url': {'uri': 'tos-cn-i-0813/xyz'},
            'author': {'sec_uid': 'MS4wLjABAAAAauthor'},
        }
        fields = DouyinAPI._comment_sticker_fields(sticker)
        self.assertEqual(fields['sticker_format'], 'gif')
        self.assertEqual(fields['sticker_author_sec_uid'], 'MS4wLjABAAAAauthor')

    def test_static_url_fallback(self):
        sticker = {'id': 1, 'static_url': {'uri': 'tos-cn-static/only'}}
        fields = DouyinAPI._comment_sticker_fields(sticker)
        self.assertEqual(fields['sticker_uri'], 'tos-cn-static/only')

    def test_missing_id_raises(self):
        with self.assertRaises(ValueError):
            DouyinAPI._comment_sticker_fields({'animate_url': {'uri': 'u'}})

    def test_missing_uri_raises(self):
        with self.assertRaises(ValueError):
            DouyinAPI._comment_sticker_fields({'id_str': '1', 'animate_url': {}})

    def test_non_dict_raises(self):
        with self.assertRaises(TypeError):
            DouyinAPI._comment_sticker_fields('not-a-dict')

    def test_sticker_format_field_name(self):
        # 已拼好的表情对象可能直接带 sticker_format（抓包实测 webp）
        fields = DouyinAPI._comment_sticker_fields(
            {'id_str': '1', 'animate_url': {'uri': 'u'}, 'sticker_format': 'webp'})
        self.assertEqual(fields['sticker_format'], 'webp')


class CustomStickersTest(unittest.TestCase):
    def test_parses_resources_stickers(self):
        payload = {
            'custom_sticker_page_list': {
                'resources': [{'stickers': [{'id_str': '1'}, {'id_str': '2'}]}],
                'next_cursor': 20,
                'is_completed': False,
            }
        }
        response = MagicMock()
        response.text = '{}'
        response.json.return_value = payload
        with patch('dy_apis.douyin_api.requests.get', return_value=response), \
                patch('dy_apis.douyin_api.HeaderBuilder') as header_builder, \
                patch('dy_apis.douyin_api.Params'):
            header_builder.return_value.build.return_value = MagicMock()
            out = DouyinAPI.get_custom_stickers(_Auth())
        self.assertEqual([s['id_str'] for s in out['stickers']], ['1', '2'])
        self.assertEqual(out['next_cursor'], 20)
        self.assertFalse(out['is_completed'])


class PublishCommentStickerTest(unittest.TestCase):
    STICKER = {
        'id': 7694150285622509605,
        'id_str': '7694150285622509605',
        'width': 800,
        'height': 800,
        'sticker_type': 2,
        'animate_url': {'uri': 'tos-cn-o-0812/abc'},
    }

    def _publish(self, **kwargs):
        with patch('dy_apis.douyin_api.HeaderBuilder') as header_builder, \
                patch('dy_apis.douyin_api.Params') as params, \
                patch('dy_apis.douyin_api.requests.post') as post, \
                patch('dy_apis.douyin_api.check_risk_response'):
            header_builder.return_value.build.return_value = MagicMock()
            response = MagicMock()
            response.json.return_value = {'status_code': 0}
            post.return_value = response
            DouyinAPI.publish_comment(_Auth(), '123', **kwargs)
            return post.call_args.kwargs['data']

    def test_sticker_fields_in_request_body(self):
        data = self._publish(content='', sticker=self.STICKER)
        self.assertEqual(data['aweme_id'], '123')
        self.assertEqual(data['text'], '')
        self.assertEqual(data['text_extra'], '[]')
        self.assertEqual(data['sticker_id'], '7694150285622509605')
        self.assertEqual(data['sticker_uri'], 'tos-cn-o-0812/abc')
        self.assertEqual(data['sticker_width'], 800)
        self.assertEqual(data['sticker_height'], 800)
        self.assertEqual(data['sticker_type'], 2)
        # 评论数据没有 animate_type，不能凭空补一个 format
        self.assertNotIn('sticker_format', data)

    def test_text_comment_has_no_sticker_fields(self):
        data = self._publish(content='普通评论')
        self.assertEqual(data['text'], '普通评论')
        for key in ('sticker_id', 'sticker_uri', 'sticker_width',
                    'sticker_height', 'sticker_type'):
            self.assertNotIn(key, data)


if __name__ == '__main__':
    unittest.main()
