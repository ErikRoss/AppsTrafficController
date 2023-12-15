#!/home/appscontroller/appstrafficcontroller/venv python

from datetime import datetime
import logging

import requests


from app import app
from cloudflare_api import CloudflareApi
from database import db
from models import Domain, Registrant
import config
from namecheap_api import NamecheapApi
import server_commands as sc


namecheap_api_params = {
    "apiuser": config.NAMECHEAP_USERNAME,
    "apikey": config.NAMECHEAP_API_KEY,
    "client_ip": config.NAMECHEAP_CLIENT_IP,
    "endpoint": config.NAMECHEAP_API_URL
    if not config.NAMECHEAP_SANDBOX
    else config.NAMECHEAP_API_SANDBOX_URL,
}


logging.basicConfig(
    filename=f"/home/appscontroller/appstrafficcontroller/logs/domains_handler_{datetime.now().strftime('%Y-%m-%d')}.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


class DomainsHandler:
    def __init__(self):
        pass

    def get_registrant_parameters(self) -> dict:
        registrant = Registrant.query.first()
        if registrant:
            registrant_parameters = {
                "RegistrantFirstName": registrant.first_name,
                "TechFirstName": registrant.first_name,
                "AdminFirstName": registrant.first_name,
                "AuxBillingFirstName": registrant.first_name,
                "RegistrantLastName": registrant.last_name,
                "AdminLastName": registrant.last_name,
                "TechLastName": registrant.last_name,
                "AuxBillingLastName": registrant.last_name,
                "RegistrantAddress1": registrant.address,
                "TechAddress1": registrant.address,
                "AdminAddress1": registrant.address,
                "AuxBillingAddress1": registrant.address,
                "RegistrantCity": registrant.city,
                "TechCity": registrant.city,
                "AdminCity": registrant.city,
                "AuxBillingCity": registrant.city,
                "RegistrantStateProvince": registrant.state_province,
                "TechStateProvince": registrant.state_province,
                "AdminStateProvince": registrant.state_province,
                "AuxBillingStateProvince": registrant.state_province,
                "RegistrantPostalCode": registrant.postal_code,
                "TechPostalCode": registrant.postal_code,
                "AdminPostalCode": registrant.postal_code,
                "AuxBillingPostalCode": registrant.postal_code,
                "RegistrantCountry": registrant.country,
                "TechCountry": registrant.country,
                "AdminCountry": registrant.country,
                "AuxBillingCountry": registrant.country,
                "RegistrantPhone": registrant.phone,
                "TechPhone": registrant.phone,
                "AdminPhone": registrant.phone,
                "AuxBillingPhone": registrant.phone,
                "RegistrantEmailAddress": registrant.email,
                "TechEmailAddress": registrant.email,
                "AdminEmailAddress": registrant.email,
                "AuxBillingEmailAddress": registrant.email,
            }
            return registrant_parameters
        else:
            return {}

    def add_domain_to_cf(self, domain: str) -> dict:
        if domain:
            cf_api = CloudflareApi()
            added = cf_api.create_zone(domain)
            if added.get("error"):
                if added["error"]["code"] == 1061:
                    nameservers = cf_api.get_zone(domain)
                    return {
                        "success": True,
                        "nameservers": nameservers["nameservers"],
                        "zone_id": nameservers["zone_id"],
                    }

                return {"success": False, "error": added["error"]}
            else:
                return {
                    "success": True,
                    "nameservers": added["nameservers"],
                    "zone_id": added["zone_id"],
                }
        else:
            return {"success": False, "error": "No domain provided."}

    def get_domain_zone(self, domain: str) -> dict:
        if domain:
            cf_api = CloudflareApi()
            zone = cf_api.get_zone(domain)
            if zone.get("error"):
                return {"success": False, "error": zone["error"]}
            else:
                return zone
        else:
            return {"success": False, "error": "No domain provided."}

    def set_dns_records_on_cf(self, zone_id: str, ip: str, name: str) -> dict:
        cf_api = CloudflareApi()
        result = cf_api.set_dns_records(zone_id, ip, name)
        return result

    def set_https_rewriting_on_cf(self, zone_id: str, state: str) -> dict:
        cf_api = CloudflareApi()
        result = cf_api.set_auto_https_rewriting(zone_id, state)
        return result

    def set_https_redirect_on_cf(self, zone_id: str, state: str) -> dict:
        cf_api = CloudflareApi()
        result = cf_api.set_always_use_https(zone_id, state)
        return result

    def redirect_domain(self, domain: Domain):
        registrant = self.get_registrant_parameters()
        namecheap_api = NamecheapApi(**namecheap_api_params)
        logging.info(f"Registering domain {domain.domain}.")
        registered = namecheap_api.register_domain(domain.domain, 1, registrant)

        if not registered["success"]:
            logging.info(f"Domain {domain.domain} not registered.")
            domain.update_status("not available")
            return False

        logging.info(f"Adding domain {domain.domain} to Cloudflare.")
        nameservers = self.add_domain_to_cf(domain.domain)
        domain.zone_id = nameservers["zone_id"]
        domain.nameservers = nameservers["nameservers"]
        logging.info(f"Domain {domain.domain} added to Cloudflare.")

        namecheap_api = NamecheapApi(**namecheap_api_params)
        ns_set = namecheap_api.set_nameservers(domain.domain, domain.nameservers)
        if ns_set["success"]:
            domain.proxied = True
            logging.info(f"Domain {domain} nameservers set.")
        else:
            domain.proxied = False
            logging.info(f"Domain {domain} nameservers not set.")

        domain_info = namecheap_api.get_domain_info(domain.domain)
        domain.created = datetime.strptime(domain_info["created"], "%m/%d/%Y")
        domain.expires = datetime.strptime(domain_info["expires"], "%m/%d/%Y")
        domain.redirected = True
        domain.status = "processing"
        db.session.commit()

        sc.add_domain_to_nginx(domain.domain, [f"www.{domain.domain}"])

    def finish_domain_registration(self, domain: Domain):
        subdomains = ["@", "www"]
        try:
            for subdomain in subdomains:
                self.set_dns_records_on_cf(
                    domain.zone_id,
                    config.DNS_HOST,
                    subdomain,
                )
            domain.redirected = True
            logging.info(f"{domain} NS records added to Cloudflare.")
        except Exception:
            pass
        else:
            set_https_rewriting = self.set_https_rewriting_on_cf(domain.zone_id, "on")

            if set_https_rewriting["success"]:
                if set_https_rewriting["result"] == "on":
                    domain.https_rewriting = True
                    logging.info(f"HTTPS rewriting enabled for domain {domain}.")
                else:
                    domain.https_rewriting = False
            else:
                domain.https_rewriting = False

            set_https_redirect = self.set_https_redirect_on_cf(domain.zone_id, "on")

            if set_https_redirect["success"]:
                if set_https_redirect["result"]["value"] == "on":
                    domain.https_redirect = True
                    logging.info(f"HTTPS redirect enabled for domain {domain}.")
                else:
                    domain.https_redirect = False
            else:
                domain.https_redirect = False

        # for subdomain in subdomains:
        #     if subdomain in ["@", "www"]:
        #         continue
        #     subdomain_obj = Subdomain(
        #         subdomain=f"{subdomain}.{domain}",
        #         status="active",
        #         expires=new_domain.expires,
        #         domain_id=new_domain.id,
        #     )
        #     db.session.add(subdomain_obj)
        #     new_domain.subdomains.append(subdomain_obj)
        #     db.session.commit()
        #     logging.info(f"Subdomain {subdomain}.{domain} added to database.")

        if all(
            [
                domain.redirected,
                domain.proxied,
                domain.https_rewriting,
                domain.https_redirect,
            ]
        ):
            logging.info(f"Domain redirected & activated: {domain.domain}.")
            domain.update_status("pending")

    def get_waiting_domains(self):
        """
        Get all waiting domains from database
        """
        domains = Domain.query.filter(Domain.status == "waiting").all()  # type: ignore
        logging.info(f"Domains to register found: {len(domains)}")
        logging.info("=========================")
        for domain in domains:
            logging.info(domain)
        logging.info("=========================")

        return domains

    def get_processing_domains(self):
        """
        Get all processing domains from database
        """
        domains = Domain.query.filter(Domain.status == "processing").all()  # type: ignore
        logging.info(f"Domains to redirect found: {len(domains)}")
        logging.info("=========================")
        for domain in domains:
            logging.info(domain)
        logging.info("=========================")

        return domains

    def get_pending_domains(self):
        """
        Get all pending domains from database
        """
        domains = Domain.query.filter(Domain.status == "pending").all()  # type: ignore
        logging.info(f"Domains to check availability found: {len(domains)}")
        logging.info("=========================")
        for domain in domains:
            logging.info(domain)
        logging.info("=========================")

        return domains

    def register_domain_at_cloudflare(self, domain):
        """
        Register domain at cloudflare
        """
        self.redirect_domain(domain)

    def register_domains_at_cloudflare(self):
        """
        Register all domains at cloudflare
        """
        with app.app_context():
            domains = self.get_waiting_domains()
            for domain in domains:
                self.register_domain_at_cloudflare(domain)

    def redirect_domains(self):
        """
        Redirect all domains from database
        """
        cf = CloudflareApi()
        with app.app_context():
            domains = self.get_processing_domains()
            for domain in domains:
                is_activated = cf.get_zone(domain.domain)["status"] != "pending"
                if is_activated:
                    self.finish_domain_registration(domain)

    def check_domain(self, domain):
        """
        Check domain by url
        """
        logging.info(f"Checking domain {domain.domain}")
        try:
            response = requests.get(f"https://{domain.domain}")
        except Exception:
            return

        if response.status_code == 200:
            domain.update_status("active")
            return

    def check_domains(self):
        """
        Check all domains from database
        """
        with app.app_context():
            domains = self.get_pending_domains()
            for domain in domains:
                self.check_domain(domain)

    def run(self):
        """
        Run domains handler
        """
        logging.info("=========================")
        logging.info("Domains handler started")
        logging.info("=========================")
        self.register_domains_at_cloudflare()
        self.redirect_domains()
        self.check_domains()
        logging.info("=========================")
        logging.info("Domains handler finished")


if __name__ == "__main__":
    domains_handler = DomainsHandler()
    domains_handler.run()
