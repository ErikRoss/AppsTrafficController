import logging
from math import log
from typing import Optional


from keitaro import KeitaroApi
from logger import save_log_message
from models import App, AppTag, Campaign


class AppsBalancer:
    def __init__(self, campaign: Optional[Campaign] = None, request: object = None):
        self.campaign = campaign
        self.request = request

    def select_app_by_weight(self):
        """
        Select app by weight
        """
        app_ids = [app["id"] for app in self.campaign.apps_stats if app["weight"] > 0]
        apps_query = (
            App.query.filter(App.id.in_(app_ids)).filter_by(status="active").all()
        )
        if not apps_query:
            return None
        
        for app in apps_query:
            if (
                self.campaign.user_id in [user.id for user in app.allowed_users]
                and app.operating_system.lower() == self.campaign.operating_system.lower()
                ):
                continue
            else:
                apps_query.remove(app)
        
        valid_app_ids = [app.id for app in apps_query]
        valid_apps_list = [
            app for app in self.campaign.apps_stats if app["id"] in valid_app_ids
        ]
        valid_apps_list = sorted(
            valid_apps_list, key=lambda app: app["visits"]
        )
        logging.info(f"Valid apps: {valid_apps_list}")
        save_log_message(
            self.__class__.__name__,
            f"Valid apps: {valid_apps_list}",
            "info"
        )

        total_visits = sum(
            [app["visits"] for app in valid_apps_list]
        )
        total_weight = sum(
            [app["weight"] for app in valid_apps_list]
        )
        
        if len(valid_apps_list) == 0:
            return None
        elif total_visits == 0 and len(valid_apps_list) > 0:
            for app in apps_query:
                if app.id == valid_apps_list[0]["id"]:
                    return app
            
            return None

        save_log_message(
            self.__class__.__name__,
            f"Total visits: {total_visits}, Total weight: {total_weight}",
            "info"
        )
        for app in valid_apps_list:
            save_log_message(
                self.__class__.__name__,
                f"App ID: {app['id']}, Visits: {app['visits']}, Weight: {app['weight']}",
                "info"
            )
            if app["visits"] == 0:
                is_overvisited = False
            else:
                is_overvisited = app["visits"] / total_visits > app["weight"] / total_weight
            if is_overvisited:
                save_log_message(
                    self.__class__.__name__,
                    f"App {app['id']} is overvisited",
                    "info"
                )
                continue
            
            save_log_message(
                self.__class__.__name__,
                f"App {app['id']} is not overvisited",
                "info"
            )
            is_unique= KeitaroApi().check_unique_app_user(
                app["keitaro_id"],
                self.request
                )
            if is_unique["result"] is True:
                save_log_message(
                    self.__class__.__name__,
                    f"App {app['id']} is unique",
                    "info"
                )
                logging.info(f"App {app['id']} is unique")
                for app_obj in apps_query:
                    if app_obj.id == app["id"]:
                        return app_obj
            else:
                save_log_message(
                    self.__class__.__name__,
                    f"App {app['id']} is not unique",
                    "info"
                )
                logging.info(f"App {app['id']} is not unique")
                continue
        else:
            save_log_message(
                self.__class__.__name__,
                "No apps found by weight",
                "info"
            )
            return None
    
    def select_app_by_tags(self):
        """
        Select app by tags
        """
        save_log_message(
            self.__class__.__name__,
            f"Select app by tags: {self.campaign.app_tags}",
            "info"
        )
        logging.info(f"Select app by tags: {self.campaign.app_tags}")
        for tag in self.campaign.app_tags:
            tag_obj = AppTag.query.filter_by(tag=tag).first()
            if not tag_obj:
                save_log_message(
                    self.__class__.__name__,
                    f"Tag {tag} not found",
                    "info"
                )
                logging.info(f"Tag {tag} not found")
                continue
            
            apps = sorted(
                tag_obj.apps, key=lambda app: app.views
            )
            save_log_message(
                self.__class__.__name__,
                f"Apps with tag {tag}: {apps}",
                "info"
            )
            logging.info(f"Apps with tag {tag}: {apps}")
            
            for app in apps:
                save_log_message(
                    self.__class__.__name__,
                    f"Check app {app.title}",
                    "info"
                )
                logging.info(f"Check app {app.title}")
                if app.status == "active":
                    if (
                        self.campaign.user_id in [user.id for user in app.allowed_users]
                        and app.operating_system.lower() 
                        == self.campaign.operating_system.lower()
                    ):
                        if KeitaroApi().check_unique_app_user(
                            app.keitaro_id,
                            self.request
                            ).get("result") is True:
                            save_log_message(
                                self.__class__.__name__,
                                f"App {app.title} is unique for user",
                                "info"
                            )
                            logging.info(f"App {app.title} is unique for user")
                            return app
                        else:
                            save_log_message(
                                self.__class__.__name__,
                                f"App {app.title} is not unique for user",
                                "info"
                            )
                            logging.info(f"App {app.title} is not unique for user")
                            continue
                    else:
                        save_log_message(
                            self.__class__.__name__,
                            f"App {app.title} is not allowed for user or OS",
                            "info"
                        )
                        logging.error(f"App {app.title} is not allowed for user or OS")
                        continue
        
        save_log_message(
            self.__class__.__name__,
            "No apps found in tags.",
            "info"
        )
        logging.info("No apps found in tags.")
        return None

    def select_reserve_app(self, operating_system=None):
        """
        Select reserve app by os and status "active"
        Return any app if no reserve app found
        """
        if not operating_system:
            operating_system = self.campaign.operating_system.lower() # type: ignore
        else:
            operating_system = operating_system.lower()
        save_log_message(
            self.__class__.__name__,
            f"Select reserve app for {operating_system}",
            "info"
        )
        logging.info(f"Select reserve app for {operating_system}")
        apps = App.query.filter_by(
            status="active", 
            operating_system=operating_system
            ).order_by(App.views.asc()).all()
        for app in apps:
            save_log_message(
                self.__class__.__name__,
                f"Check app {app.title}",
                "info"
            )
            logging.info(f"Check app {app.title}")
            
            if self.campaign and app.id not in self.campaign.apps or not self.campaign:
                is_user_unique = KeitaroApi().check_unique_app_user(
                    app.keitaro_id,
                    self.request
                    ).get("result")
                if is_user_unique:
                    save_log_message(
                        self.__class__.__name__,
                        f"App {app.title} is unique for user",
                        "info"
                    )
                    logging.info(f"App {app.title} is unique for user")
                    return app
                else:
                    save_log_message(
                        self.__class__.__name__,
                        f"App {app.title} is not unique for user",
                        "info"
                    )
                    logging.info(f"App {app.title} is not unique for user")
                    continue
            else:
                save_log_message(
                    self.__class__.__name__,
                    f"App {app.title} is already in campaign",
                    "info"
                )
                logging.info(f"App {app.title} is already in campaign")
                continue
        else:
            save_log_message(
                self.__class__.__name__,
                "No apps found with OS.",
                "info"
            )
            logging.info("No apps found with OS.")
            return None

    def select_relevant_app(self):
        """
        Select relevant app for campaign by weight or tags 
        or reserve app if no relevant app found
        """
        if not self.campaign:
            save_log_message(
                self.__class__.__name__,
                "No campaign found.",
                "info"
            )
            return None
        
        save_log_message(
            self.__class__.__name__,
            f"Select relevant app for campaign {self.campaign.title}",
            "info"
        )
        logging.info(f"Select relevant app for campaign {self.campaign.title}")
        if self.campaign.apps_stats:
            selected_app = self.select_app_by_weight()
            if selected_app:
                save_log_message(
                    self.__class__.__name__,
                    f"Selected app by weight: {selected_app.id}",
                    "info"
                )
                logging.info(f"Selected app by weight: {selected_app.id}")
                return selected_app
        elif self.campaign.app_tags:
            selected_app = self.select_app_by_tags()
            if selected_app:
                save_log_message(
                    self.__class__.__name__,
                    f"Selected app by tags: {selected_app.id}",
                    "info"
                )
                logging.info(f"Selected app by tags: {selected_app.id}")
                return selected_app

        save_log_message(
            self.__class__.__name__,
            "No apps with campaign weight or tags found. Select reserve app by OS",
            "info"
        )
        logging.info("No apps with campaign weight or tags found. Select reserve app by OS")
        selected_app = self.select_reserve_app()
        if selected_app:
            save_log_message(
                self.__class__.__name__,
                f"Selected reserve app: {selected_app.id}",
                "info"
            )
            logging.info(f"Selected reserve app: {selected_app.id}")
            return selected_app
        else:
            save_log_message(
                self.__class__.__name__,
                "No reserve apps found.",
                "info"
            )
            logging.info("No reserve apps found.")
            return None
