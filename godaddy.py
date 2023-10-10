import json
from time import sleep
from typing import Any, Callable, Dict
import requests


def retry_on_rate_limit_error(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator that retries the API call if it raises a rate limit error.
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        while True:
            result = func(*args, **kwargs)
            if result.status_code != 429:
                return result.json()
            else:
                # Rate limit error, wait for the specified time and try again
                retry_after = int(result.json()['retryAfterSec'])
                print(f'Rate limit exceeded, waiting for {retry_after} seconds...')
                sleep(retry_after)
    return wrapper


class goDaddyApi:   
    def __init__(self):
        self.api_key = '3mM44UdBCk9NNt_C4txQSFB6oZEwTwyKwM3hc'
        self.api_secret = 'STayMezLQVJ36xi8i7vWQm'
        self.test_api_endpoint = 'https://api.ote-godaddy.com'
        self.api_endpoint = 'https://api.godaddy.com'
        self.headers = {
            'Authorization': f'sso-key {self.api_key}:{self.api_secret}',
            'Content-Type': 'application/json'
        }

    @retry_on_rate_limit_error
    def get_all_domains(self) -> requests.Response:
        """
        Get all domains from GoDaddy account
        
        Returns:
            requests.Response: response from API
        """
        response = requests.get(f'{self.test_api_endpoint}/v1/domains', headers=self.headers)
        
        return response
    
    @retry_on_rate_limit_error
    def is_domain_available(self, domain: str) -> requests.Response:
        """
        Check if domain is available
        
        Args:
            domain (str): domain to check
            
        Returns:
            requests.Response: response from API
        """
        response = requests.get(
            f'{self.test_api_endpoint}/v1/domains/available?domain={domain}', 
            headers=self.headers
            )
        
        return response
    
    @retry_on_rate_limit_error
    def get_domain_dns(self, domain: str) -> requests.Response:
        """
        Get domain DNS
        
        Args:
            domain (str): domain to get DNS from
            
        Returns:
            requests.Response: response from API
        """
        response = requests.get(
            f'{self.test_api_endpoint}/v1/domains/{domain}/records', 
            headers=self.headers
            )
        
        return response
    
    @retry_on_rate_limit_error
    def add_dns_to_domain(self, domain: str) -> requests.Response:
        """
        Add DNS to domain
        
        Args:
            domain (str): domain to add DNS to
            
        Returns:
            requests.Response: response from API
        """
        data = [
            {
                "data": "string",
                "name": "string",
                "port": 65535,
                "priority": 0,
                "protocol": "string",
                "service": "string",
                "ttl": 0,
                "type": "A",
                "weight": 0
            }
        ]
        
        response = requests.patch(
            f'{self.test_api_endpoint}/v1/domains/{domain}/records', 
            headers=self.headers, 
            json=data
            )
        
        return response
    
    @retry_on_rate_limit_error
    def replace_dns_to_domain(self, domain: str) -> requests.Response:
        """
        Replace DNS to domain
        
        Args:
            domain (str): domain to replace DNS to
            
        Returns:
            requests.Response: response from API
        """
        data = [
            {
                "data": "string",
                "name": "string",
                "port": 65535,
                "priority": 0,
                "protocol": "string",
                "service": "string",
                "ttl": 0,
                "type": "A",
                "weight": 0
            }
        ]
        
        response = requests.put(
            f'{self.test_api_endpoint}/v1/domains/{domain}/records', 
            headers=self.headers, 
            json=data
            )
        
        return response
    
    @retry_on_rate_limit_error
    def purchase_domain(self, domain) -> requests.Response:
        """
        Buy domain
        
        Args:
            domain (str): domain to buy
            
        Returns:
            requests.Response: response from API
        """
        data = {
            "consent": {
            "agreedAt": "string",
            "agreedBy": "string",
            "agreementKeys": [
            "string"
            ]
        },
        "contactAdmin": {
            "addressMailing": {
            "address1": "string",
            "address2": "string",
            "city": "string",
            "country": "US",
            "postalCode": "string",
            "state": "string"
            },
            "email": "user@example.com",
            "fax": "string",
            "jobTitle": "string",
            "nameFirst": "string",
            "nameLast": "string",
            "nameMiddle": "string",
            "organization": "string",
            "phone": "string"
        },
        "contactBilling": {
            "addressMailing": {
            "address1": "string",
            "address2": "string",
            "city": "string",
            "country": "US",
            "postalCode": "string",
            "state": "string"
            },
            "email": "user@example.com",
            "fax": "string",
            "jobTitle": "string",
            "nameFirst": "string",
            "nameLast": "string",
            "nameMiddle": "string",
            "organization": "string",
            "phone": "string"
        },
        "contactRegistrant": {
            "addressMailing": {
            "address1": "string",
            "address2": "string",
            "city": "string",
            "country": "US",
            "postalCode": "string",
            "state": "string"
            },
            "email": "user@example.com",
            "fax": "string",
            "jobTitle": "string",
            "nameFirst": "string",
            "nameLast": "string",
            "nameMiddle": "string",
            "organization": "string",
            "phone": "string"
        },
        "contactTech": {
            "addressMailing": {
            "address1": "string",
            "address2": "string",
            "city": "string",
            "country": "US",
            "postalCode": "string",
            "state": "string"
            },
            "email": "user@example.com",
            "fax": "string",
            "jobTitle": "string",
            "nameFirst": "string",
            "nameLast": "string",
            "nameMiddle": "string",
            "organization": "string",
            "phone": "string"
        },
        "domain": "google.com",
        "nameServers": [
            "string"
        ],
        "period": 1,
        "privacy": False,
        "renewAuto": True
        }
        
        response = requests.post(
            f'{self.test_api_endpoint}/v1/domains/purchase', 
            headers=self.headers, 
            json=json.dumps({'body': data})
            )
        
        return response
        
        
if __name__ == '__main__':
    api = goDaddyApi()
    print(api.get_domain_dns('google.com'))