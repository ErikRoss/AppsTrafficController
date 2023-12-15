#!/home/appscontroller/appstrafficcontroller/venv python

from datetime import datetime
import logging
import requests
from sqlalchemy import not_

from models import App


logging.basicConfig(
    filename=f"/home/appscontroller/appstrafficcontroller/logs/apps_ban_checker_{datetime.now().strftime('%Y-%m-%d')}.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


class AppsChecker:
    def __init__(self):
        logging.info("=========================")
        logging.info("Apps checker started")
        self.apps = self.get_all_apps()

    def get_all_apps(self):
        """
        Get all not "banned" status apps from database
        """
        apps = App.query.filter(not_(App.status == "banned")).all()
        logging.info(f"Apps to check found: {len(apps)}")
        logging.info("=========================")
        for app in apps:
            logging.info(app)
        logging.info("=========================")

        return apps

    def check_apps(self):
        """
        Check all apps from database
        """
        for app in self.apps:
            self.check_app(app)

    def check_app(self, app):
        """
        Check app by url
        """
        logging.info(f"Checking app {app}")
        try:
            response = requests.get(app.url)

            is_error_section = b'id="error-section"' in response.content
            if response.status_code != 200 or is_error_section:
                self.ban_app(app)
                logging.info(f"App {app} banned")
        except Exception:
            self.ban_app(app)
            logging.info(f"App {app} banned")
        else:
            logging.info(f"App {app} checked")

    def ban_app(self, app):
        """
        Ban app
        """
        app.update_status("banned")

    def run(self):
        """
        Run apps checker
        """
        self.check_apps()
        logging.info("=========================")
        logging.info("Apps checker finished")


if __name__ == "__main__":
    apps_checker = AppsChecker()
    apps_checker.run()
