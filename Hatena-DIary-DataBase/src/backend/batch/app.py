import os
import boto3
import requests
from bs4 import BeautifulSoup
from batch.parser import parse_html_content
from common.models import ReviewItem

# 設定の取得
SSM_PARAM_NAME = os.environ.get('SSM_PARAM_NAME', '/hatena-batch/api_key')
HATENA_ID = os.environ.get('HATENA_ID')
BLOG_ID = os.environ.get('BLOG_ID')
# 環境変数が空の場合に備えて直接テーブル名を指定
TABLE_NAME = os.environ.get('REVIEW_TABLE_NAME', 'HatenaBlogReviews')

ssm = boto3.client('ssm')
dynamodb = boto3.resource('dynamodb')

# 無限ループ・想定外の大量ページ取得を防ぐための取得ページ数上限
MAX_PAGES = 1000

def lambda_handler(event: any, context: any) -> str:
    print("★バッチ処理を開始します★")

    # 1. APIキー取得
    param = ssm.get_parameter(Name=SSM_PARAM_NAME, WithDecryption=True)
    api_key = param['Parameter']['Value']

    # 2. ブログデータ取得（Atomフィードの<link rel="next">を辿り過去ページも取得）
    url = f"https://blog.hatena.ne.jp/{HATENA_ID}/{BLOG_ID}/atom/entry"
    all_reviews = []
    page_count = 0

    while url and page_count < MAX_PAGES:
        response = requests.get(url, auth=(HATENA_ID, api_key))
        response.raise_for_status()
        page_count += 1

        # 3. 解析
        xml_soup = BeautifulSoup(response.content, 'xml')
        entries = xml_soup.find_all('entry')

        for entry in entries:
            published = entry.find('published').text
            date_str = published.split('T')[0]
            content = entry.find('content').text

            reviews = parse_html_content(content, date_str)
            all_reviews.extend(reviews)

        next_link = xml_soup.find('link', rel='next')
        url = next_link['href'] if next_link else None

    if url:
        print(f"警告：ページ上限（{MAX_PAGES}）に達したため打ち切りました。まだ次ページが存在します。")

    print(f"解析完了：{page_count}ページ、{len(all_reviews)}件の抽出データを取得しました")

    # 4. 解析が成功した後に、既存データを全削除（ページネーションを考慮して全件走査）
    table = dynamodb.Table(TABLE_NAME)
    deleted_count = 0
    with table.batch_writer() as batch:
        scan_kwargs = {"ProjectionExpression": "id"}
        while True:
            resp = table.scan(**scan_kwargs)
            for item in resp["Items"]:
                batch.delete_item(Key={"id": item["id"]})
                deleted_count += 1
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    print(f"既存データを{deleted_count}件削除しました")

    # 5. 新データを全件書き込み
    with table.batch_writer() as batch:
        for rev in all_reviews:
            batch.put_item(Item=rev)

    print(f"★処理完了：{len(all_reviews)}件を新規保存しました★")
    return {"statusCode": 200, "body": f"Saved {len(all_reviews)} items."}