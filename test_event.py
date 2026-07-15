import unittest
from types import SimpleNamespace
from unittest.mock import patch

with patch("threading.Thread.start"):
    from . import event


class MediaInfoTest(unittest.TestCase):
    def test_falls_back_to_subscriptions(self):
        responses = [
            SimpleNamespace(json=lambda: {"data": []}),
            SimpleNamespace(json=lambda: {"data": [{"tmdb_id": "1632181", "poster_path": "/poster.jpg"}]}),
        ]
        config = SimpleNamespace(nextfind_base_url="https://nextfind.example/api", nextfind_api_key="key")

        with patch.object(event, "config", config), patch.object(event.httpx, "get", side_effect=responses) as get:
            item = event.NextFindLogNotifier.__new__(event.NextFindLogNotifier).media_info(
                {"title": "不期而遇的姐妹", "tmdb_id": "1632181"}
            )

        self.assertEqual(item["poster_path"], "/poster.jpg")
        self.assertTrue(get.call_args_list[1].args[0].endswith("/subscriptions"))


if __name__ == "__main__":
    unittest.main()
