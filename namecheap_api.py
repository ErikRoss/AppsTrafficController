from pprint import pprint
from typing import Any, Dict, List

import requests
import xmltodict


class NamecheapApi:
    def __init__(
        self, apiuser: str, apikey: str, client_ip: str, endpoint: str
    ) -> None:
        self.request_url = f"{endpoint}?ApiUser={apiuser}&ApiKey={apikey}&UserName={apiuser}&ClientIp={client_ip}"

    def send_request(self, command: str, params: Dict[str, Any]) -> requests.Response:
        """
        Send request to Namecheap API

        Args:
            command (str): API command to execute
            params (Dict[str, Any]): parameters to pass to API command

        Returns:
            requests.Response: response from API
        """
        params["Command"] = command
        if len(params) < 11:
            response = requests.get(self.request_url, params=params)
        else:
            print("POST")
            response = requests.post(self.request_url, data=params)

        return response

    def convert_response_to_dict(self, response: requests.Response) -> Dict[str, Any]:
        """
        Convert XML response to dict

        Args:
            response (requests.Response): response from API

        Returns:
            Dict[str, Any]: response converted to dict
        """
        return xmltodict.parse(response.text)

    def get_domains_list(self) -> Dict[str, Any]:
        """
        Get list of domains

        Returns:
            Dict[str, Any]: response from API
        """
        response = self.send_request("namecheap.domains.getList", {})
        response_dict = self.convert_response_to_dict(response)

        if response_dict["ApiResponse"]["Errors"]:
            return {"error": response_dict["ApiResponse"]["Errors"]["Error"]["#text"]}

        return response_dict["ApiResponse"]["CommandResponse"]["DomainGetListResult"]

    def get_domain_info(self, domain: str) -> Dict[str, Any]:
        """
        Get domain info

        Args:
            domain (str): domain to get info for

        Returns:
            Dict[str, Any]: response from API
        """
        response = self.send_request(
            "namecheap.domains.getInfo", {"DomainName": domain}
        )
        response_dict = self.convert_response_to_dict(response)

        if response_dict["ApiResponse"]["Errors"]:
            return {"error": response_dict["ApiResponse"]["Errors"]["Error"]["#text"]}

        result = response_dict["ApiResponse"]["CommandResponse"]["DomainGetInfoResult"]
        domain_info = {
            "name": result["@DomainName"],
            "created": result["DomainDetails"]["CreatedDate"],
            "expires": result["DomainDetails"]["ExpiredDate"],
            "nameservers": result["DnsDetails"]["Nameserver"],
        }

        return domain_info

    def get_domain_dns_hosts(
        self, domain: str
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        """
        Get domain DNS hosts

        Args:
            domain (str): domain to get DNS hosts for

        Returns:
            List[Dict[str, Any]]|Dict[str, Any]: hosts list or error dict
        """
        sld, tld = domain.rsplit(".", 1)
        response = self.send_request(
            "namecheap.domains.dns.getHosts", {"SLD": sld, "TLD": tld}
        )
        response_dict = self.convert_response_to_dict(response)

        if response_dict["ApiResponse"]["Errors"]:
            return {"error": response_dict["ApiResponse"]["Errors"]["Error"]["#text"]}

        result = response_dict["ApiResponse"]["CommandResponse"][
            "DomainDNSGetHostsResult"
        ]["host"]
        hosts = []
        for host in result:
            hosts.append(
                {
                    "HostName": host["@Name"],
                    "RecordType": host["@Type"],
                    "Address": host["@Address"],
                    "TTL": host["@TTL"],
                }
            )

        return hosts

    def check_domains_availability(self, domains: list) -> Dict[str, Any]:
        """
        Check domains availability

        Args:
            domains (list): list of domains to check

        Returns:
            Dict[str, Any]: response from API
        """
        result = {}

        response = self.send_request("namecheap.domains.check", {"DomainList": domains})
        response_dict = self.convert_response_to_dict(response)

        if response_dict["ApiResponse"]["Errors"]:
            return {"error": response_dict["ApiResponse"]["Errors"]["Error"]["#text"]}

        domains = response_dict["ApiResponse"]["CommandResponse"]["DomainCheckResult"]
        if isinstance(domains, dict):
            result = {domains["@Domain"]: domains["@Available"] == "true"}  # type: ignore
        else:
            for domain in domains:
                result[domain["@Domain"]] = domain["@Available"] == "true"

        return result

    def register_domain(
        self, domain: str, years: int = 1, customer_parameters: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """
        Register domain

        Args:
            domain (str): domain to register
            years (int, optional): number of years to register. Defaults to 1.
            customer_parameters (Dict[str, Any], optional): custom parameters to pass to API.
            Defaults to {}.

        Returns:
            Dict[str, Any]: response from API
        """
        params = {"DomainName": domain, "Years": years}
        params.update(customer_parameters)

        response = self.send_request("namecheap.domains.create", params)
        response_dict = self.convert_response_to_dict(response)

        if response_dict["ApiResponse"]["Errors"]:
            return {
                "error": response_dict["ApiResponse"]["Errors"]["Error"]["#text"],
                "success": False,
            }

        result = response_dict["ApiResponse"]["CommandResponse"]["DomainCreateResult"]
        result_dict = {
            "domain": result["@Domain"],
            "success": result["@Registered"] == "true",
        }

        return result_dict

    def set_domain_dns_hosts(self, params: dict) -> Dict[str, Any]:
        """
        Set domain DNS to point to IP address

        Args:
            domain (str): domain to set DNS for
            ip_address (str): IP address to point domain to

        Returns:
            Dict[str, Any]: response from API
        """
        response = self.send_request("namecheap.domains.dns.setHosts", params)
        response_dict = self.convert_response_to_dict(response)

        if response_dict["ApiResponse"]["Errors"]:
            return {"error": response_dict["ApiResponse"]["Errors"]["Error"]["#text"]}

        return {"success": True}

    def set_nameservers(self, domain: str, nameservers: list) -> Dict[str, Any]:
        """
        Set domain nameservers

        Args:
            domain (str): domain to set nameservers for
            nameservers (list): list of nameservers to set

        Returns:
            Dict[str, Any]: response from API
        """
        sld, tld = domain.rsplit(".", 1)
        params = {"SLD": sld, "TLD": tld, "Nameservers": ",".join(nameservers)}

        response = self.send_request("namecheap.domains.dns.setCustom", params)
        response_dict = self.convert_response_to_dict(response)
        pprint(response_dict)

        if response_dict["ApiResponse"]["Errors"]:
            return {
                "success": False,
                "error": response_dict["ApiResponse"]["Errors"]["Error"]["#text"],
            }

        return {"success": True}


if __name__ == "__main__":
    pass
    # customer_parameters = {
    #     'RegistrantFirstName': 'Erik',
    #     'RegistrantLastName': 'Ross',
    #     'RegistrantAddress1': '123 Main St',
    #     'RegistrantCity': 'Denver',
    #     'RegistrantStateProvince': 'CO',
    #     'RegistrantPostalCode': '80202',
    #     'RegistrantCountry': 'US',
    #     'RegistrantPhone': '+1.3035555555',
    #     'RegistrantEmailAddress': 'example@example.com',
    #     'TechFirstName': 'Erik',
    #     'TechLastName': 'Ross',
    #     'TechAddress1': '123 Main St',
    #     'TechCity': 'Denver',
    #     'TechStateProvince': 'CO',
    #     'TechPostalCode': '80202',
    #     'TechCountry': 'US',
    #     'TechPhone': '+1.3035555555',
    #     'TechEmailAddress': 'example@example.com',
    #     'AdminFirstName': 'Erik',
    #     'AdminLastName': 'Ross',
    #     'AdminAddress1': '123 Main St',
    #     'AdminCity': 'Denver',
    #     'AdminStateProvince': 'CO',
    #     'AdminPostalCode': '80202',
    #     'AdminCountry': 'US',
    #     'AdminPhone': '+1.3035555555',
    #     'AdminEmailAddress': 'example@example.com',
    #     'AuxBillingFirstName': 'Erik',
    #     'AuxBillingLastName': 'Ross',
    #     'AuxBillingAddress1': '123 Main St',
    #     'AuxBillingCity': 'Denver',
    #     'AuxBillingStateProvince': 'CO',
    #     'AuxBillingPostalCode': '80202',
    #     'AuxBillingCountry': 'US',
    #     'AuxBillingPhone': '+1.3035555555',
    #     'AuxBillingEmailAddress': 'example@example.com',
    #     }
