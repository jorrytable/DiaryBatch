import sys
print(sys.path)

from src.backend.batch.parser import parse_html_content

def test_kanryo():
    # 実験用のニセ日記データ
    test_html = "<h3>*** 今日見たもの</h3><ul><li><a href='http://x.com'>テスト動画</a><ul><li>面白かった</li></ul></li></ul>"
    kekka = parse_html_content(test_html, "2026-01-05")

    # ちゃんと1件抜き出せたか確認
    assert len(kekka) == 1
    assert kekka[0]['title'] == "テスト動画"
    print("\n★テスト成功！正しく抜き出せています★")