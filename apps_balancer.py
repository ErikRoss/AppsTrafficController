import logging
from keitaro import KeitaroApi
from models import App, Campaign


class AppsBalancer:
    def __init__(self, campaign: Campaign, request: object = None):
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
            if self.campaign.user_id in [user.id for user in app.allowed_users]:
                continue
            else:
                apps_query.remove(app)
        
        valid_app_ids = [app.id for app in apps_query]
        valid_apps_list = [
            app for app in self.campaign.apps_stats if app["id"] in valid_app_ids
        ]

        total_visits = sum(
            [app["visits"] for app in valid_apps_list]
        )
        if total_visits == 0:
            return valid_apps_list[0]["id"]

        for app in valid_apps_list:
            is_overvisited = app["visits"] / total_visits > app["weight"] / 100
            if is_overvisited:
                continue
            is_visited = KeitaroApi().check_unique_app_user(
                app["keitaro_id"],
                self.request
                )
            if is_visited:
                continue
            else:
                return app["id"]
        else:
            return None

    def select_reserve_app(self):
        """
        Select reserve app by tags, os and status "active"
        Return any app if no reserve app found
        """
        for tag in self.campaign.app_tags:
            apps = tag.apps
            for app in apps:
                if (
                    app.operating_system == self.campaign.operating_system
                    and app.status == "active"
                ):
                    if (
                        self.campaign.user_id in [user.id for user in app.allowed_users]
                        and app.id not in self.campaign.apps
                        
                    ):
                        if KeitaroApi().check_unique_app_user(
                            app.keitaro_id,
                            self.request
                            ).get("result") is True:
                            return app.id
                        else:
                            continue
                    else:
                        continue
        else:
            apps = App.query.filter_by(
                status="active", operating_system=self.campaign.operating_system
            ).all()
            for app in apps:
                if (
                    KeitaroApi().check_unique_app_user(
                        app.keitaro_id,
                        self.request
                        ).get("result") is True
                    and app.id not in self.campaign.apps
                ):
                    return app.id
                else:
                    continue
            else:
                return None

    def select_relevant_app(self):
        """
        Select relevant app
        """
        logging.info(f"Select relevant app for campaign {self.campaign.title}")
        if self.campaign.apps_stats:
            selected_app = self.select_app_by_weight()
            logging.info(f"Selected app by weight: {selected_app}")
            return selected_app
        else:
            logging.info("No apps with weight found. Select reserve app")
            selected_app = self.select_reserve_app()
            logging.info(f"Selected reserve app: {selected_app}")
            return selected_app
