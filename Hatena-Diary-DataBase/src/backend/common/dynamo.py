def paginate(fn, **kwargs):
    """DynamoDBのquery/scanのように`LastEvaluatedKey`を返すページネーション形式の
    呼び出しを、`LastEvaluatedKey`が無くなるまで繰り返し、全Itemsを1つのイテレータとして返す。"""
    while True:
        response = fn(**kwargs)
        yield from response.get("Items", [])
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
