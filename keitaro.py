import json
import logging
import re
from typing import Optional
from flask import app
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

    def add_stream_to_campaign(self, app_name: str, app_id: Optional[int] = None):
        """
        Add app to campaign
        """
        url = f"{self.api_url}/streams"
        payload = {
            "campaign_id": self.campaign_id,
            "schema": "action",
            "type": "regular",
            "name": f"{app_id} - {app_name}",
            "action_type": "do_nothing",
            "filters": [
                {"name": "uniqueness", "mode": "accept", "payload": "stream"},
                {"name": "sub_id_1", "mode": "accept", "payload": str(app_id)},
                {"name": "uniqueness", "mode": "accept", "payload": "stream"},
            ],
        }

        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()["id"]

    def get_stream(self, stream_id: int):
        """
        Get stream
        """
        url = f"{self.api_url}/streams/{stream_id}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def set_stream_deleted(self, stream_id: int):
        """
        Set stream deleted
        """
        stream_data = self.get_stream(stream_id)
        stream_data["name"] = f"{stream_data['name']} DELETED"
        stream_data["state"] = "disabled"

        url = f"{self.api_url}/streams/{stream_id}"
        response = requests.put(url, headers=self.headers, json=stream_data)
        return response.json()

    def check_is_user_bot(self, request, request_parameters, rma, clid, fbclid, domain, ulb):
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
            "rma": rma,
            "clid": clid,
            "fbclid": fbclid,
            "domain": f"https://{domain}",
            "ulb": ulb,
        }
        params.update(request_parameters)

        result = requests.get(url, params=params)
        if result.status_code == 200:
            params["result"] = result.json()["body"]

            geo = None
            device = None
            log = result.json()["log"]
            for row in log:
                if row.startswith("User info: "):
                    user_info = row.split("User info: ")[1]
                    user_info = json.loads(user_info)
                    geo = user_info["Country"]
                    device = user_info["OS"]
                    kclid = user_info["SubID"]
                    break
            params["geo"] = geo.lower() if geo else "Unknown"
            params["device"] = device.lower() if device else "Unknown"
            params["kclid"] = kclid if kclid else "Unknown"

            return params
        else:
            params["result"] = "error"
            return params

    def check_unique_app_user(self, stream_id, request, param=None) -> dict:
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
            "stream_id": stream_id,
            "log": "1",
            "info": "1",
            "ip": client_ip,
            "user_agent": user_agent,
            "language": language,
            "x_requested_with": x_requested_with,
            "param": param,
        }

        result = requests.get(url, params=params)

        if result.status_code != 200:
            params["result"] = "error"
            return params

        try:
            logs = result.json()["log"]
            if param:
                logging.info(f"Keitaro logs with param {param}:")
            else:
                logging.info("Keitaro logs:")
            logging.info(logs)
            for index, row in enumerate(logs):
                if row.endswith(f"#{stream_id}"):
                    filtered = logs[index + 1]
                    if "sub_id_1" in filtered:
                        params["result"] = True
                        return params
                    elif "uniqueness" in filtered:
                        params["result"] = False
                        return params
                    else:
                        params["result"] = False
                        return params
            else:
                params["result"] = False
                return params
        except Exception as e:
            logging.error(e)
            return {"result": False}

    def set_user_ununique(self, stream_id, request=None, param=None):
        self.check_unique_app_user(stream_id, request, param)


if __name__ == "__main__":
    api = KeitaroApi()
    # print(api.check_unique_user(16))
    # print(api.add_stream_to_campaign("test_app2"))
    # print(api.check_is_user_bot())
    # print(api.check_unique_app_user(128))
    # print(api.set_user_ununique(128))
    api.set_stream_deleted(167)

    # api.get_campaigns()
