import os
import boto3
import json
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
        # DateIndex（data_type固定値 + review_dateソートキー）に対してQueryし、
        # DynamoDB側で日付降順ソート済みの全件を取得する
        response = table.query(
            IndexName='DateIndex',
            KeyConditionExpression=Key('data_type').eq('review'),
            ScanIndexForward=False
        )
        items = response.get('Items', [])

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"  # 画面から呼ぶために必要
            },
            "body": json.dumps(items, ensure_ascii=False)
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to fetch data"})
        }