import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TestChatListMessagesReScope(unittest.TestCase):
    def test_list_chat_messages_does_not_shadow_re(self):
        from starlette.requests import Request

        import wechat_decrypt_tool.routers.chat as chat

        class _Sentinel(Exception):
            pass

        def fake_collect_chat_messages(**_kwargs):
            merged = [
                {
                    "id": "1",
                    "sortSeq": 0,
                    "createTime": 1,
                    "localId": 1,
                    "type": 266287972401,
                    "_rawText": "<msg><template>${wxid_abc}</template></msg>",
                    "renderType": "appmsg",
                }
            ]
            return merged, False, [], [], set()

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/chat/messages",
            "raw_path": b"/api/chat/messages",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        request = Request(scope)

        with TemporaryDirectory() as td:
            account_dir = Path(td) / "acc"
            account_dir.mkdir(parents=True, exist_ok=True)

            sentinel = _Sentinel("stop-after-template-parse")

            with patch.object(chat, "_resolve_account_dir", return_value=account_dir), patch.object(
                chat, "_iter_message_db_paths", return_value=[account_dir / "msg_0.db"]
            ), patch.object(chat, "_collect_chat_messages", side_effect=fake_collect_chat_messages), patch.object(
                chat, "_postprocess_transfer_messages", lambda _merged: None
            ), patch.object(chat, "_extract_xml_tag_text", return_value="${wxid_abc}"), patch.object(
                chat, "_load_contact_rows", side_effect=sentinel
            ):
                with self.assertRaises(_Sentinel):
                    chat.list_chat_messages(
                        request=request,
                        username="44372432598@chatroom",
                        account="acc",
                        source="decrypted",
                    )

    def test_list_chat_messages_filters_by_time_range(self):
        from starlette.requests import Request

        import wechat_decrypt_tool.routers.chat as chat

        rows = [
            {"id": "1", "sortSeq": 0, "createTime": 1000, "localId": 1, "type": 1, "renderType": "text", "content": "old"},
            {"id": "2", "sortSeq": 0, "createTime": 2000, "localId": 2, "type": 1, "renderType": "text", "content": "mid"},
            {"id": "3", "sortSeq": 0, "createTime": 3000, "localId": 3, "type": 1, "renderType": "text", "content": "new"},
        ]

        def fake_collect_chat_messages(**_kwargs):
            return [dict(r) for r in rows], False, [], [], set()

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/chat/messages",
            "raw_path": b"/api/chat/messages",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        request = Request(scope)

        with TemporaryDirectory() as td:
            account_dir = Path(td) / "acc"
            account_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(chat, "_resolve_account_dir", return_value=account_dir), patch.object(
                chat, "_iter_message_db_paths", return_value=[account_dir / "msg_0.db"]
            ), patch.object(chat, "_collect_chat_messages", side_effect=fake_collect_chat_messages), patch.object(
                chat, "_postprocess_transfer_messages", lambda _merged: None
            ), patch.object(chat, "_load_contact_rows", return_value={}), patch.object(
                chat, "_query_head_image_usernames", return_value=[]
            ), patch.object(chat, "_load_group_nickname_map", return_value={}), patch.object(
                chat, "_load_enterprise_contact_info", return_value={}
            ):
                resp = chat.list_chat_messages(
                    request=request,
                    username="wxid_friend",
                    account="acc",
                    source="decrypted",
                    start_time=1500,
                    end_time=2500,
                    limit=10,
                )

        self.assertEqual(resp["status"], "success")
        self.assertEqual([m["id"] for m in resp["messages"]], ["2"])


if __name__ == "__main__":
    unittest.main()

