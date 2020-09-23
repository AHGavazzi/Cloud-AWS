import argparse
import json
import logging
import sys
from logging.handlers import RotatingFileHandler

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
handler = RotatingFileHandler(
    "./get_registered_accounts.log", maxBytes=20971520, backupCount=5
)
formatter = logging.Formatter("%(levelname)-8s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def set_auth_header(auth_token: str) -> dict:
    """
    Creates the auth header for requests
    :param auth_token
    :return: dict
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + auth_token,
    }
    return headers


def check_account_access(auth_token: str, accounts: list) -> list:
    """
    Performs an Access Verification check on the specified AWS Account IDs


    :param auth_token:
    :param accounts:
    :return: dict:
    :example:

    Example check_account_access (token, ['12344667', '345678865'])
    """
    if len(accounts) > 0:
        params = []
        for account in accounts:
            params.append("ids=" + account)
            param_string = "&".join(params)
    url = "https://api.crowdstrike.com/cloud-connect-aws/entities/verify-account-access/v1?" + param_string
    headers = set_auth_header(auth_token)
    logger.debug("url:" + url)
    logger.debug("headers:" + json.dumps(headers, indent=2))
    try:
        r = requests.post(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.debug("HTTP error {} calling {}".format(err, url))
    except Exception as e:
        logger.debug("Failed to create accounts")
    r_content = json.loads(r.text)
    # accounts are listed in response[]
    return r_content["resources"]


def get_falcon_discover_accounts(sortby=None, filterby=None) -> bool:
    good_accounts = []
    bad_accounts = []

    url = "https://api.crowdstrike.com/cloud-connect-aws/combined/accounts/v1"
    PARAMS = {"limit": "100"}
    if filterby:
        PARAMS.update({"filter": filterby})
    if sortby:
        PARAMS.update({"sort": sortby})

    auth_token = get_auth_token()
    if auth_token:
        auth_header = get_auth_header(auth_token)
    else:
        print("Failed to auth token")
        sys.exit(1)
    headers = {
        "Content-Type": "application/json",
    }
    headers.update(auth_header)

    try:
        response = requests.request("GET", url, headers=headers, params=PARAMS)
        response_content = json.loads(response.text)
        logger.info("Response to register = {}".format(response_content))
    except Exception as e:
        logger.info("Got exception {}".format(e))
        return

    good_exit = 200
    if response.status_code == good_exit:
        accounts_list = response_content["resources"]
        accounts_to_test = []
        for account in accounts_list:
            accounts_to_test.append(account['id'])
            # print(json.dumps(account, indent=4))
        results = check_account_access(auth_token, accounts_to_test)
        for result in results:
            if result.get('successful'):
                print(f'Account {result.get("id")} is ok!')
            else:
                print(f'Account {result.get("id")} has a problem {result.get("reason")}')
                account_values_to_check = {
                    'id': account.get('id'),
                    'iam_role_arn': account.get('iam_role_arn'),
                    'external_id': account.get('external_id'),
                    'cloudtrail_bucket_owner_id': account.get('cloudtrail_bucket_owner_id'),
                    'cloudtrail_bucket_region': account.get('cloudtrail_bucket_region'),
                }
                print(f'Current settings {json.dumps(account_values_to_check, indent=4)}')
    else:
        error_code = response.status_code
        error_msg = response_content["errors"][0]["message"]
        logger.info(
            "Got response error code {} message {}".format(error_code, error_msg)
        )
        return


def get_auth_header(auth_token) -> str:
    if auth_token:
        auth_header = "Bearer " + auth_token
        headers = {"Authorization": auth_header}
        return headers


def get_auth_token():
    url = "https://api.crowdstrike.com/oauth2/token"
    payload = "client_secret=" + falcon_client_secret + "&client_id=" + falcon_client_id
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.ok:
        response_object = response.json()
        token = response_object.get("access_token", "")
        if token:
            return token
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Get Params to send notification to CRWD topic"
    )

    parser.add_argument(
        "-f", "--falcon_client_id", help="Falcon Client ID", required=True
    )
    parser.add_argument(
        "-s", "--falcon_client_secret", help="Falcon Client Secret", required=True
    )
    args = parser.parse_args()
    falcon_client_id = args.falcon_client_id
    falcon_client_secret = args.falcon_client_secret
    get_falcon_discover_accounts()
