import os
import boto3
import json
import gzip
import base64
from boto3.dynamodb.conditions import Key

from common.dynamo import paginate

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
        items = list(paginate(
            table.query,
            IndexName="FeedIndex",
            KeyConditionExpression=Key("data_type").eq("review"),
            ScanIndexForward=False,
        ))

        # Lambdaの同期呼び出し応答は6MBまでという上限があり、embed_html/OGP情報等の
        # 増加でJSONが年々肥大化しているため、gzip圧縮してBase64文字列として返す。
        # （API GatewayのBinary MediaTypes機能は使わない。設定するとCORSプリフライト
        #  =OPTIONSのMock統合の応答まで巻き込まれて500エラーになったため。
        #  isBase64Encodedを使わずbodyを普通の文字列として返せばAPI Gatewayは
        #  一切関与せずそのままフロントに届くので、フロント側でbase64デコード＋
        #  gunzipする方式にしている）
        body_bytes = json.dumps(items, ensure_ascii=False).encode('utf-8')
        compressed = gzip.compress(body_bytes)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/plain",
                "Access-Control-Allow-Origin": "*"  # 画面から呼ぶために必要
            },
            "body": base64.b64encode(compressed).decode('ascii')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to fetch data"})
        }