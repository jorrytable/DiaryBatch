import os
import boto3

SSM_PARAM_NAME = os.environ.get('SSM_PARAM_NAME', '/hatena-site/access-token')

ssm = boto3.client('ssm')


def lambda_handler(event, context):
    """
    Authorizationヘッダーの値をSSMパラメータストアの秘密値と比較し、
    一致すればAllow、不一致ならDenyのIAMポリシーを返すTOKEN Authorizer。
    """
    token = event.get('authorizationToken', '')

    param = ssm.get_parameter(Name=SSM_PARAM_NAME, WithDecryption=True)
    expected = param['Parameter']['Value']

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
