import json
import requests


class CloudflareApi:
    def __init__(self):
        api_token = "xkBpn4tp3HtNxmEXK4QPzpCYjaNx9MVF4OrQXTzA"
        account_id = "e8f5ac44c2848ca0c24e4c8bad429901"
        self.api_host = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self.params = {"account": {"id": account_id}}

    def create_zone(self, domain_name, zone_type="full"):
        endpoint = "/zones"
        url = self.api_host + endpoint
        data = {"name": domain_name, "type": zone_type}
        data.update(self.params)

        response = requests.post(url, headers=self.headers, data=json.dumps(data))

        if response.status_code != 200:
            result = response.json()["errors"][0]
            return {"success": False, "error": result}
        else:
            name_servers = response.json()["result"]["name_servers"]
            zone_id = response.json()["result"]["id"]
            return {"success": True, "nameservers": name_servers, "zone_id": zone_id}

    def get_zone(self, domain_name):
        endpoint = "/zones"
        url = self.api_host + endpoint
        params = {"name": domain_name}
        params.update(self.params)

        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code != 200:
            result = response.json()["errors"][0]
            return {"error": result}
        else:
            result = response.json()["result"]
            print(result)
            nameservers = []
            zone_id = ""
            for zone in result:
                if zone["name"] == domain_name:
                    nameservers = zone["name_servers"]
                    zone_id = zone["id"]

            return {
                "success": True, 
                "nameservers": nameservers, 
                "zone_id": zone_id,
                "status": zone["status"]
                }

    def set_dns_records(self, zone_id: str, ip: str, name: str):
        endpoint = f"/zones/{zone_id}/dns_records"
        url = self.api_host + endpoint
        data = {
            "content": ip,
            "name": name,
            "proxied": True,
            "type": "A",
            "comment": "Created by AppsTrafficController",
            "ttl": 3600,
        }

        response = requests.post(url, headers=self.headers, data=json.dumps(data))
        if response.status_code != 200:
            result = response.json()["errors"][0]
            if result["code"] == 81057:
                return {"success": True, "result": result}
            return {"success": False, "error": result}
        else:
            result = response.json()["result"]
            return {"success": True, "result": result}

    def set_auto_https_rewriting(self, zone_id: str, state: str):
        endpoint = f"/zones/{zone_id}/settings/automatic_https_rewrites"
        url = self.api_host + endpoint
        data = {"value": state}

        response = requests.patch(url, headers=self.headers, data=json.dumps(data))
        if response.status_code != 200:
            result = response.json()["errors"][0]
            return {"error": result}
        else:
            result = response.json()["result"]["value"]
            return {"success": True, "result": result}

    def set_always_use_https(self, zone_id: str, state: str):
        endpoint = f"/zones/{zone_id}/settings/always_use_https"
        url = self.api_host + endpoint
        data = {"value": state}

        response = requests.patch(url, headers=self.headers, data=json.dumps(data))
        if response.status_code != 200:
            result = response.json()["errors"][0]
            return {"error": result}
        else:
            result = response.json()["result"]
            return {"success": True, "result": result}


if __name__ == "__main__":
    api = CloudflareApi()
    api.create_zone("appctrle.online")
