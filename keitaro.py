import requests


class KeitaroApi:
    def __init__(self):
        self.api_token = "373b09e70fca029d92005c89f984c155"
        self.api_url = "https://track.premastex.online/admin_api/v1"
        self.campaign_id = 16
        self.campaign_token = "pfsy8gkrpjcdqdb6yyq3hcbkgj3r9vz8"
        self.headers = {"Content-Type": "application/json", "Api-Key": self.api_token}

    def get_campaigns(self):
        """
        Get campaigns
        """
        url = f"{self.api_url}/campaigns"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def get_stream_actions(self):
        """
        Get stream actions
        """
        url = f"{self.api_url}/streams_actions"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def add_stream_to_campaign(self, app_name: str):
        """
        Add app to campaign
        """
        url = f"{self.api_url}/streams"
        payload = {
            "campaign_id": self.campaign_id,
            "schema": "action",
            "type": "regular",
            "name": app_name,
            "action_type": "do_nothing",
        }

        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()["id"]

    def check_is_user_bot(self, request=None):
        """
        Check user is bot
        """
        url = "https://track.premastex.online/click_api/v3"

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        user_agent = request.headers.get("User-Agent")
        language = request.headers.get("Accept-Language")
        x_requested_with = request.headers.get("X-Requested-With")
        # client_ip = "188.163.96.228"
        # user_agent = "Mozilla/5.0 (Linux; Android 10; SM-A205F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36"
        # language = "en-US,en;q=0.9,ru;q=0.8"
        # x_requested_with = "XMLHttpRequest"

        params = {
            "token": "4jfksyvprpsxxykcxpzcjkqxzptwmtr2",
            "log": "1",
            "info": "1",
            "ip": client_ip,
            "user_agent": user_agent,
            "language": language,
            "x_requested_with": x_requested_with,
        }

        result = requests.get(url, params=params)
        if result.status_code == 200:
            params["result"] = result.json()["body"]
            return params
        else:
            params["result"] = "error"
            return params

    def check_unique_app_user(self, stream_id, request=None):
        """
        Check unique users
        """
        url = "https://track.premastex.online/click_api/v3"

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        user_agent = request.headers.get("User-Agent")
        language = request.headers.get("Accept-Language")
        x_requested_with = request.headers.get("X-Requested-With")
        # client_ip = "188.163.96.228"
        # user_agent = "Mozilla/5.0 (Linux; Android 10; SM-A205F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36"
        # language = "en-US,en;q=0.9,ru;q=0.8"
        # x_requested_with = "XMLHttpRequest"

        params = {
            "token": self.campaign_token,
            "campaign_id": self.campaign_id,
            "stream_id": 95,
            "log": "1",
            "info": "1",
            "ip": client_ip,
            "user_agent": user_agent,
            "language": language,
            "x_requested_with": x_requested_with,
        }

        result = requests.get(url, params=params)
        if result.status_code == 200:
            params["result"] = result.json()["info"]["uniqueness"]["stream"]
            return params
        else:
            params["result"] = "error"
            return params


if __name__ == "__main__":
    api = KeitaroApi()
    # print(api.check_unique_user(16))
    print(api.add_stream_to_campaign("test_app2"))
    print(api.check_is_user_bot())
    print(api.check_unique_app_user(95))
    # api.get_campaigns()
