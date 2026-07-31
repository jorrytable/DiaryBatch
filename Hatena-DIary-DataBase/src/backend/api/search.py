import os
import boto3
import json
import gzip
import base64
from boto3.dynamodb.conditions import Key

# 設定
TABLE_NAME = os.environ.get('REVIEW_TABLE_NAME', 'HatenaBlogReviews')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    フロントエンドからのリクエストを受けて、DynamoDBからデータを返す
    """
    try:
        # FeedIndex（data_type固定値 + review_dateソートキー）に対してQueryし、
        # DynamoDB側で日付降順ソート済みの全件を取得する。
        # 1回のQuery応答は1MBまでのため、LastEvaluatedKeyがある間は続けて取得する
        items = []
        query_kwargs = {
            "IndexName": "FeedIndex",
            "KeyConditionExpression": Key("data_type").eq("review"),
            "ScanIndexForward": False,
        }
        while True:
            response = table.query(**query_kwargs)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        # Lambdaの同期呼び出し応答は6MBまでという上限があり、embed_html/OGP情報等の
        # 増加でJSONが年々肥大化しているため、gzip圧縮してBase64で返す。
        # fetch()はContent-Encoding: gzipを自動でデコードするためフロント側の変更は不要
        # （API Gateway側はBinaryMediaTypesの設定でこのバイナリ応答をパススルーする）。
        body_bytes = json.dumps(items, ensure_ascii=False).encode('utf-8')
        compressed = gzip.compress(body_bytes)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
                "Access-Control-Allow-Origin": "*"  # 画面から呼ぶために必要
            },
            "isBase64Encoded": True,
            "body": base64.b64encode(compressed).decode('ascii')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to fetch data"})
        }