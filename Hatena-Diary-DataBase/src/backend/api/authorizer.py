import os
import boto3

SSM_PARAM_NAME = os.environ.get('SSM_PARAM_NAME', '/hatena-site/access-token')

ssm = boto3.client('ssm')

# Lambdaのウォームコンテナ間で使い回すキャッシュ。リクエストのたびにSSM(+KMS復号)を
# 呼ぶのを避けるため、初回のみ取得する（合言葉のローテーションはコールドスタートまで反映されない）。
_cached_expected_token = None


def _get_expected_token():
    global _cached_expected_token
    if _cached_expected_token is None:
        param = ssm.get_parameter(Name=SSM_PARAM_NAME, WithDecryption=True)
        _cached_expected_token = param['Parameter']['Value']
    return _cached_expected_token


def lambda_handler(event, context):
    """
    Authorizationヘッダーの値をSSMパラメータストアの秘密値と比較し、
    一致すればAllow、不一致ならDenyのIAMポリシーを返すTOKEN Authorizer。
    """
    token = event.get('authorizationToken', '')

    expected = _get_expected_token()

    effect = 'Allow' if token == expected else 'Deny'

    return {
        'principalId': 'hatena-diary-user',
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': event['methodArn']
                }
            ]
        }
    }
