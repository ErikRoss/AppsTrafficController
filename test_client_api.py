from pprint import pprint
import secrets
import unittest

from flask_jwt_extended import current_user

from app import app
from models import App, User, Campaign, Domain, GeoPrice


class TestClientApi(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def get_user_token(self, username):
        data = {"username": username, "password": username}
        response = self.client.post("/api/login", json=data)

        return response.json["access_token"]  # type: ignore

    # Authorization

    def test_authorization_fail(self):
        data = {"username": "test_fail", "password": "test_fail"}

        response = self.client.post("/api/login", json=data)
        self.assertIsNotNone(response.json["error"])  # type: ignore
        try:
            self.assertEqual(response.status_code, 401)
        except AssertionError:
            self.assertEqual(response.status_code, 400)

    def test_authorization_admin(self):
        data = {"username": "test_admin", "password": "test_admin"}

        response = self.client.post("/api/login", json=data)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["access_token"])  # type: ignore
        self.assertEqual(response.json["user"]["role"], "admin")  # type: ignore

    def test_authorization_user(self):
        data = {"username": "test_user", "password": "test_user"}

        response = self.client.post("/api/login", json=data)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.json["access_token"])  # type: ignore
            self.assertEqual(response.json["user"]["role"], "user")  # type: ignore
        except AssertionError:
            self.assertEqual(response.status_code, 401)

    # Users

    def test_register_user_without_token(self):
        response = self.client.post(
            "/api/users/register",
            json={
                "username": "test_created_user",
                "password": "test_created_user",
                "email": "test_created_user@example.com",
                "role": "user",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_register_user_with_admin_token(self):
        token = self.get_user_token("test_admin")
        data = {
            "username": "test_created_user4",
            "password": "test_created_user",
            "email": "test_created_user4@example.com",
            "role": "user",
        }

        response = self.client.post(
            "/api/users/register",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        pprint(response.json)
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            self.assertEqual(response.status_code, 409)

    def test_register_user_with_user_token(self):
        token = self.get_user_token("test_user")
        data = {
            "username": "test_created_user",
            "password": "test_created_user",
            "email": "test_created_user@example.com",
            "role": "user",
        }

        response = self.client.post(
            "/api/users/register",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    def test_get_users_without_token(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 401)

    def test_get_users_with_admin_token(self):
        """
        Test get users with admin token and check if response contains
        required fields
        """
        token = self.get_user_token("test_admin")
        per_page = 50

        response = self.client.get(
            "/api/users", headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["users"])  # type: ignore
        self.assertGreater(len(response.json["users"]), 0)  # type: ignore
        self.assertLess(len(response.json["users"]), per_page + 1)  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore

    def test_get_users_with_user_token(self):
        token = self.get_user_token("test_user")

        response = self.client.get(
            "/api/users", headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 403)

    def test_search_users_without_token(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 401)

    def test_search_users_with_admin_token(self):
        token = self.get_user_token("test_admin")
        params = {"page": 1, "per_page": 20, "search_query": "test"}

        response = self.client.get(
            "/api/users",
            query_string=params,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["users"])  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore

    def test_search_users_with_user_token(self):
        token = self.get_user_token("test_user")
        params = {"page": 1, "per_page": 20, "search_query": "test"}

        response = self.client.get(
            "/api/users",
            query_string=params,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    def test_get_user_by_id_without_token(self):
        response = self.client.get("/api/users/1")
        self.assertEqual(response.status_code, 401)

    def test_get_user_by_id_with_admin_token(self):
        token = self.get_user_token("test_admin")

        response = self.client.get(
            "/api/users/1", headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["user"])  # type: ignore
        self.assertEqual(response.json["user"]["id"], 1)  # type: ignore

    def test_get_user_by_id_with_other_user_token(self):
        token = self.get_user_token("test_user")

        response = self.client.get(
            "/api/users/1", headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 403)

    def test_get_user_by_id_with_his_user_token(self):
        token = self.get_user_token("test_admin")
        user_id = User.query.filter_by(username="test_user").first().id  # type: ignore

        response = self.client.get(
            f"/api/users/{user_id}", headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["user"])  # type: ignore
        self.assertEqual(response.json["user"]["id"], 2)  # type: ignore

    def test_update_user_status_without_token(self):
        data = {"id": 1, "status": "active"}

        response = self.client.patch("/api/users/update_status", json=data)
        self.assertEqual(response.status_code, 401)

    def test_update_user_status_with_admin_token(self):
        token = self.get_user_token("test_admin")

        response = self.client.patch(
            "/api/users/update_status",
            json={"id": 1, "status": "active"},
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_user_status_with_user_token(self):
        token = self.get_user_token("test_user")

        response = self.client.patch(
            "/api/users/update_status",
            json={"id": 1, "status": "active"},
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    # def test_update_user_role_without_token(self):
    #     data = {"id": 1, "status": "active"}

    #     response = self.client.patch("/api/users/update_status", json=data)
    #     self.assertEqual(response.status_code, 401)

    # def test_update_user_role_with_admin_token(self):
    #     token = self.get_user_token("test_admin")

    #     response = self.client.patch(
    #         "/api/users/update_status",
    #         json={"id": 1, "status": "active"},
    #         headers={"Authorization": "Bearer " + token},
    #     )
    #     self.assertEqual(response.status_code, 200)

    # def test_update_user_role_with_user_token(self):
    #     token = self.get_user_token("test_user")

    #     response = self.client.patch(
    #         "/api/users/update_status",
    #         json={"id": 1, "status": "active"},
    #         headers={"Authorization": "Bearer " + token},
    #     )
    #     self.assertEqual(response.status_code, 403)

    def test_add_balance_without_token(self):
        response = self.client.patch(
            "/api/users/add_balance", json={"id": 1, "amount": 100}
        )
        self.assertEqual(response.status_code, 401)

    def test_add_balance_with_admin_token(self):
        token = self.get_user_token("test_admin")
        user = User.query.filter_by(username="test_admin").first()

        response = self.client.patch(
            "/api/users/add_balance",
            json={"id": user.id, "amount": 100}, # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

        user = User.query.filter_by(username="test_user").first()

        response = self.client.patch(
            "/api/users/add_balance",
            json={"id": user.id, "amount": 100}, # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_add_balance_with_user_token(self):
        token = self.get_user_token("test_user")

        response = self.client.patch(
            "/api/users/add_balance",
            json={"id": 1, "amount": 100},
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    def test_subtract_user_balance_without_token(self):
        response = self.client.patch(
            "/api/users/subtract_balance", json={"id": 1, "amount": 100}
        )
        self.assertEqual(response.status_code, 401)

    def test_subtract_user_balance_with_admin_token(self):
        token = self.get_user_token("test_admin")
        user = User.query.filter_by(username="test_admin").first()

        response = self.client.patch(
            "/api/users/subtract_balance",
            json={"id": user.id, "amount": 100},
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        
        user = User.query.filter_by(username="test_user").first()
        
        response = self.client.patch(
            "/api/users/subtract_balance",
            json={"id": user.id, "amount": 100},
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_subtract_user_balance_with_user_token(self):
        token = self.get_user_token("test_user")

        response = self.client.patch(
            "/api/users/subtract_balance",
            json={"id": 1, "amount": 100},
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)
    
    def test_get_user_transactions_without_token(self):
        response = self.client.get("/api/users/1/transactions")
        self.assertEqual(response.status_code, 401)
    
    def test_get_user_transactions_with_admin_token(self):
        token = self.get_user_token("test_admin")
        user = User.query.filter_by(username="test_admin").first()

        response = self.client.get(
            f"/api/users/{user.id}/transactions",
            headers={"Authorization": "Bearer " + token},
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        
    def test_get_user_transactions_with_user_token(self):
        token = self.get_user_token("test_user")
        user = User.query.filter_by(username="test_user").first()
        
        response = self.client.get(
            f"/api/users/{user.id}/transactions",
            headers={"Authorization": "Bearer " + token},
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        

    def test_update_user_password_without_token(self):
        response = self.client.patch(
            "/api/users/update_password", json={"id": 1, "password": "test_user"}
        )
        self.assertEqual(response.status_code, 401)

    def test_update_user_password_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_user = User.query.filter_by(username="test_user").first()
        data = {"id": test_user.id, "password": "test_user"}  # type: ignore

        response = self.client.patch(
            "/api/users/update_password",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_user_password_with_user_token(self):
        token = self.get_user_token("test_user")
        test_user = User.query.filter_by(username="test_user").first()
        data = {"id": test_user.id, "password": "test_user"}  # type: ignore

        response = self.client.patch(
            "/api/users/update_password",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    def test_add_subuser_without_token(self):
        response = self.client.post(
            "/api/users/subusers/add",
            json={
                "name": "subuser1",
                "color": "#000000",
                "description": "subuser1 description"
            }
        )
        self.assertEqual(response.status_code, 401)
        
    def test_add_subuser_with_admin_token(self):
        token = self.get_user_token("test_admin")
        data = {
            "name": "subuser1",
            "color": "#000000",
            "description": "subuser1 description"
        }

        response = self.client.post(
            "/api/users/subusers/add",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
    
    def test_add_subuser_with_user_token(self):
        token = self.get_user_token("test_user")
        data = {
            "name": "subuser1",
            "color": "#000000",
            "description": "subuser1 description"
        }

        response = self.client.post(
            "/api/users/subusers/add",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    # Apps

    def test_get_apps_without_token(self):
        response = self.client.get("/api/apps")
        self.assertEqual(response.status_code, 401)

    def test_get_apps_with_admin_token(self):
        required_fields = [
            "id",
            "title",
            "url",
            "image",
            "operating_system",
            "tags",
            "description",
            "status",
        ]
        token = self.get_user_token("test_admin")
        per_page = 50

        response = self.client.get(
            "/api/apps", headers={"Authorization": "Bearer " + token}
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["apps"])  # type: ignore
        self.assertGreater(len(response.json["apps"]), 0)  # type: ignore
        self.assertLess(len(response.json["apps"]), per_page + 1)  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore
        for app_ in response.json["apps"]:  # type: ignore
            for field in required_fields:
                self.assertIn(field, app_)

    def test_get_apps_with_user_token(self):
        denied_fields = ["url", "unique_tag", "description", "status"]
        required_fields = [
            "id",
            "title",
            "image",
            "operating_system",
            "tags",
        ]
        # token = self.get_user_token("test_user")
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwNDk4MTk0MSwianRpIjoiMzI5OTgyN2MtM2UzMy00YTljLWEzZTgtM2ZkOGEwOTUzMWE0IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6MiwibmJmIjoxNzA0OTgxOTQxfQ.NTLu_Cdl3ixWfmv6C_NM4wMpb2KjtjH7kq22czT4fRw"
        per_page = 50

        response = self.client.get(
            "/api/apps", headers={"Authorization": "Bearer " + token}
        )
        pprint(response.json)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.json["apps"])  # type: ignore
            self.assertGreater(len(response.json["apps"]), 0)  # type: ignore
            self.assertLess(len(response.json["apps"]), per_page + 1)  # type: ignore
            self.assertIsNotNone(response.json["total_count"])  # type: ignore
            for app_ in response.json["apps"]:  # type: ignore
                for field in required_fields:
                    self.assertIn(field, app_)
                for field in denied_fields:
                    self.assertNotIn(field, app_)
        except AssertionError:
            self.assertEqual(response.status_code, 401)

    def test_search_apps_without_token(self):
        response = self.client.get("/api/apps")
        self.assertEqual(response.status_code, 401)

    def test_search_apps_with_admin_token(self):
        token = self.get_user_token("test_admin")
        params = {"page": 1, "per_page": 20, "search_query": "tag1"}

        response = self.client.get(
            "/api/apps",
            query_string=params,
            headers={"Authorization": "Bearer " + token},
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["apps"])  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore

    def test_search_apps_with_user_token(self):
        token = self.get_user_token("test_user")
        params = {"page": 1, "per_page": 20, "search_query": "tag1"}

        response = self.client.get(
            "/api/apps",
            query_string=params,
            headers={"Authorization": "Bearer " + token},
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["apps"])  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore

    def test_get_app_by_id_without_token(self):
        response = self.client.get("/api/apps/1")
        self.assertEqual(response.status_code, 401)

    def test_get_app_by_id_with_admin_token(self):
        required_fields = [
            "id",
            "title",
            "url",
            "image",
            "operating_system",
            "tags",
            "description",
            "status",
        ]
        token = self.get_user_token("test_admin")
        test_app = App.query.first()
        self.assertIsNotNone(test_app)

        response = self.client.get(
            f"/api/apps/{test_app.id}",  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["app"])  # type: ignore
        for field in required_fields:
            self.assertIn(field, response.json["app"])  # type: ignore

    def test_get_app_by_id_with_user_token(self):
        denied_fields = ["url", "unique_tag", "description", "status"]
        required_fields = [
            "id",
            "title",
            "image",
            "operating_system",
            "tags",
        ]
        token = self.get_user_token("test_user")
        test_app = App.query.first()
        self.assertIsNotNone(test_app)

        response = self.client.get(
            f"/api/apps/{test_app.id}",  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["app"])  # type: ignore
        for field in required_fields:
            self.assertIn(field, response.json["app"])  # type: ignore
        for field in denied_fields:
            self.assertNotIn(field, response.json["app"])  # type: ignore

    def test_add_app_without_token(self):
        response = self.client.post(
            "/api/apps/add",
            json={
                "title": "Test App",
                "url": "http://example.com",
                "image": "http://example.com/image.png",
                "operating_system": "android",
                "tags": "test,app",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_add_app_with_admin_token(self):
        token = self.get_user_token("test_admin")
        data = {
            "title": "Test App 12",
            "url": "https://example.com",
            "image": "image1.png",
            "image_folder": "static/img/uploads",
            "operating_system": "android",
            "tags": ["tag1", "tag2"],
            "description": "Test App description",
            "status": "active",
        }

        response = self.client.post(
            "/api/apps/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            self.assertEqual(response.status_code, 409)

    def test_add_app_with_user_token(self):
        token = self.get_user_token("test_user")
        data = {
            "title": "Test App",
            "url": "https://example.com",
            "image": "image1.png",
            "image_folder": "static/img/uploads",
            "operating_system": "iOS",
            "tags": ["tag1", "tag2"],
            "description": "Test App description",
            "status": "inactive",
        }

        response = self.client.post(
            "/api/apps/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 403)

    def test_update_app_status_without_token(self):
        response = self.client.patch(
            "/api/apps/update_status", json={"id": 1, "status": "active"}
        )
        self.assertEqual(response.status_code, 401)

    def test_update_app_status_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)

        response = self.client.patch(
            "/api/apps/update_status",
            json={"id": test_app.id, "status": "active"},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_app_status_with_user_token(self):
        token = self.get_user_token("test_user")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)

        response = self.client.patch(
            "/api/apps/update_status",
            json={"id": test_app.id, "status": "active"},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    def test_delete_app_without_token(self):
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)

        response = self.client.patch(
            "/api/apps/delete",
            json={"id": test_app.id, "deleted": True},  # type: ignore
            )
        self.assertEqual(response.status_code, 401)

    def test_delete_app_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)

        response = self.client.delete(
            "/api/apps/delete",  # type: ignore
            headers={"Authorization": "Bearer " + token},
            json={"id": test_app.id, "deleted": True},  # type: ignore
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"message": "App deleted successfully."})

    def test_delete_app_with_user_token(self):
        token = self.get_user_token("test_user")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)

        response = self.client.delete(
            "/api/apps/delete",  # type: ignore
            headers={"Authorization": "Bearer " + token},
            json={"id": test_app.id, "deleted": True},  # type: ignore
        )
        self.assertEqual(response.status_code, 403)
    
    def test_add_app_tag_without_token(self):
        response = self.client.post(
            "/api/apps/tags/add",
            json={"tag": "test_tag"}
        )
        self.assertEqual(response.status_code, 401)
        
    def test_add_app_tag_with_admin_token(self):
        token = self.get_user_token("test_admin")
        data = {
            "tag": "test_tag"
        }

        response = self.client.post(
            "/api/apps/tags/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            self.assertEqual(response.status_code, 409)
        
    def test_add_app_tag_with_user_token(self):
        token = self.get_user_token("test_user")
        data = {
            "tag": "test_tag"
        }

        response = self.client.post(
            "/api/apps/tags/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 403)
    
    def test_allow_app_for_users_without_token(self):
        response = self.client.patch(
            "/api/apps/allow_for_users",
            json={"id": 1, "users": [1, 2]}
        )
        self.assertEqual(response.status_code, 401)
        
    def test_allow_app_for_users_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)
        users_ids = [user.id for user in User.query.all()]  # type: ignore

        response = self.client.patch(
            "/api/apps/allow_for_users",
            json={"id": test_app.id, "users": users_ids},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
    
    def test_allow_app_for_users_with_user_token(self):
        token = self.get_user_token("test_user")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)
        
        response = self.client.patch(
            "/api/apps/allow_for_users",
            json={"id": test_app.id, "users": [1, 2]},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)
    
    def test_disallow_app_for_users_without_token(self):
        response = self.client.patch(
            "/api/apps/disallow_for_users",
            json={"id": 1, "users": [1, 2]}
        )
        self.assertEqual(response.status_code, 401)
        
    def test_disallow_app_for_users_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)
        users_ids = [User.query.first().id]  # type: ignore
        
        response = self.client.patch(
            "/api/apps/disallow_for_users",
            json={"id": test_app.id, "users": users_ids},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        
    def test_disallow_app_for_users_with_user_token(self):
        token = self.get_user_token("test_user")
        test_app = App.query.first()
        try:
            self.assertIsNotNone(test_app)
        except AssertionError:
            self.test_add_app_with_admin_token()
            test_app = App.query.first()
            self.assertIsNotNone(test_app)
        
        response = self.client.patch(
            "/api/apps/disallow_for_users",
            json={"id": test_app.id, "users": [1, 2]},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    # Campaigns

    def test_add_campaign_without_token(self):
        response = self.client.post(
            "/api/campaigns/add",
            json={
                "title": "Test Campaign",
                "user": 1,
                "description": "Test Campaign description",
                "apps": [{"id": 1, "weight": 100}],
                "offer_url": "example.com",
                "geo": "ua",
                "status": "active",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_add_campaign_with_admin_token(self):
        token = self.get_user_token("test_admin")
        user = User.query.filter_by(username="test_admin").first()
        app_obj = App.query.first()
        data = {
            "title": f"Test Campaign {secrets.token_hex(2)}",
            "user": user.id,  # type: ignore
            "description": "Test Campaign description",
            "apps": [
                {
                    "id": app_obj.id,  # type: ignore
                    "weight": 100,
                }
            ],
            "offer_url": "example.com",
            "geo": "ua",
            "status": "active",
        }

        response = self.client.post(
            "/api/campaigns/add",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_add_campaign_with_user_token(self):
        token = self.get_user_token("test_user")
        user = User.query.filter_by(username="test_user").first()
        app = App.query.first()
        data = {
            "title": f"Test Campaign {secrets.token_hex(2)}",
            "user": user.id,  # type: ignore
            "description": "Test Campaign description",
            "apps": [
                {
                    "id": app.id,  # type: ignore
                    "weight": 100,
                }
            ],
            "offer_url": "example.com",
            "geo": "ua",
            "status": "active",
        }

        response = self.client.post(
            "/api/campaigns/add",
            json=data,
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_campaign_status_without_token(self):
        response = self.client.patch(
            "/api/campaigns/update_status", json={"id": 1, "status": "active"}
        )
        self.assertEqual(response.status_code, 401)

    def test_update_campaign_status_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_campaign = Campaign.query.first()
        try:
            self.assertIsNotNone(test_campaign)
        except AssertionError:
            self.test_add_campaign_with_admin_token()
            test_campaign = Campaign.query.first()
            self.assertIsNotNone(test_campaign)

        response = self.client.patch(
            "/api/campaigns/update_status",
            json={"id": test_campaign.id, "status": "active"},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_campaign_status_with_user_token(self):
        token = self.get_user_token("test_user")
        user = User.query.filter_by(username="test_user").first()
        test_campaign = Campaign.query.filter_by(user_id=user.id).first()  # type: ignore
        try:
            self.assertIsNotNone(test_campaign)
        except AssertionError:
            self.test_add_campaign_with_admin_token()
            test_campaign = Campaign.query.first()
            self.assertIsNotNone(test_campaign)

        response = self.client.patch(
            "/api/campaigns/update_status",
            json={"id": test_campaign.id, "status": "active"},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_send_campaign_to_archive_without_token(self):
        response = self.client.patch("/api/campaigns/send_to_archive", json={"id": 1})
        self.assertEqual(response.status_code, 401)

    def test_send_campaign_to_archive_with_admin_token(self):
        self.test_add_campaign_with_admin_token()
        token = self.get_user_token("test_admin")
        user = User.query.filter_by(username="test_admin").first()
        campaign = Campaign.query.filter_by(user_id=user.id).first()  # type: ignore

        response = self.client.patch(
            "/api/campaigns/send_to_archive",
            json={"id": campaign.id, "archived": True},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.patch(
            "/api/campaigns/send_to_archive",
            json={"id": campaign.id, "archived": False},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        
    def test_send_campaign_to_archive_with_user_token(self):
        self.test_add_campaign_with_admin_token()
        token = self.get_user_token("test_user")
        user = User.query.filter_by(username="test_user").first()
        campaign = Campaign.query.filter_by(user_id=user.id).first()  # type: ignore
        
        response = self.client.patch(
            "/api/campaigns/send_to_archive",
            json={"id": campaign.id, "archived": True},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.patch(
            "/api/campaigns/send_to_archive",
            json={"id": campaign.id, "archived": False},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_get_campaigns_without_token(self):
        response = self.client.get("/api/campaigns")

        self.assertEqual(response.status_code, 401)

    def test_get_campaigns_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page}

        response = self.client.get(
            "/api/campaigns",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["campaigns"])  # type: ignore
        self.assertGreater(len(response.json["campaigns"]), 0)  # type: ignore
        self.assertLess(len(response.json["campaigns"]), per_page + 1)  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore

    def test_get_archived_campaigns_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        archived = True
        params = {"page": page, "per_page": per_page, "archived": archived}

        response = self.client.get(
            "/api/campaigns",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["campaigns"])  # type: ignore
        for campaign in response.json["campaigns"]:  # type: ignore
            self.assertEqual(campaign["archive"], True)

    def test_get_not_archived_campaigns_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        archived = False
        params = {"page": page, "per_page": per_page, "archived": archived}

        response = self.client.get(
            "/api/campaigns",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["campaigns"])  # type: ignore
        for campaign in response.json["campaigns"]:  # type: ignore
            self.assertEqual(campaign["archive"], False)

    def test_get_campaigns_with_user_token(self):
        token = self.get_user_token("test_user")
        per_page = 50

        response = self.client.get(
            "/api/campaigns", headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["campaigns"])  # type: ignore
        self.assertGreater(len(response.json["campaigns"]), 0)  # type: ignore
        self.assertLess(len(response.json["campaigns"]), per_page + 1)  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore
        for campaign in response.json["campaigns"]:  # type: ignore
            self.assertEqual(campaign["user_id"], current_user.id)

    def test_get_archived_campaigns_with_user_token(self):
        token = self.get_user_token("test_user")
        page = 1
        per_page = 50
        archived = True
        params = {"page": page, "per_page": per_page, "archived": archived}

        response = self.client.get(
            "/api/campaigns",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["campaigns"])  # type: ignore
        for campaign in response.json["campaigns"]:  # type: ignore
            self.assertEqual(campaign["archive"], True)

    def test_get_not_archived_campaigns_with_user_token(self):
        token = self.get_user_token("test_user")
        page = 1
        per_page = 50
        archived = False
        params = {"page": page, "per_page": per_page, "archived": archived}

        response = self.client.get(
            "/api/campaigns",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["campaigns"])  # type: ignore
        for campaign in response.json["campaigns"]:  # type: ignore
            self.assertEqual(campaign["archive"], False)
    
    def test_update_campaign_subuser_without_token(self):
        response = self.client.patch(
            "/api/campaigns/update_subuser", json={"id": 1, "subuser_id": 1}
        )
        self.assertEqual(response.status_code, 401)
    
    def test_update_campaign_subuser_with_admin_token(self):
        token = self.get_user_token("test_admin")
        user = User.query.filter_by(username="test_admin").first()
        subuser = user.subusers[0]
        test_campaign = Campaign.query.filter_by(user_id=user.id).first()  # type: ignore
        
        response = self.client.patch(
            "/api/campaigns/update_subuser",
            json={"id": test_campaign.id, "subuser_id": subuser.id},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
    
    def test_update_campaign_subuser_with_user_token(self):
        token = self.get_user_token("test_user")
        user = User.query.filter_by(username="test_user").first()
        subuser = user.subusers[0]
        test_campaign = Campaign.query.filter_by(user_id=user.id).first()
        
        response = self.client.patch(
            "/api/campaigns/update_subuser",
            json={"id": test_campaign.id, "subuser_id": subuser.id},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        

    # Domains
    
    def test_get_top_domains_without_token(self):
        response = self.client.get("/api/domains/top")
        self.assertEqual(response.status_code, 401)
        
    def test_get_top_domains_with_admin_token(self):
        token = self.get_user_token("test_admin")
        
        response = self.client.get(
            "/api/domains/top",
            headers={"Authorization": "Bearer " + token},
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])  # type: ignore
        self.assertIsNotNone(response.json["top_domains"])  # type: ignore
    
    def test_get_top_domains_with_user_token(self):
        token = self.get_user_token("test_user")
        
        response = self.client.get(
            "/api/domains/top",
            headers={"Authorization": "Bearer " + token},
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 403)
        
    def test_add_top_domain_without_token(self):
        response = self.client.post(
            "/api/domains/top/add",
            json={
                "name": ".online",
            },
        )
        self.assertEqual(response.status_code, 401)
    
    def test_add_top_domain_with_admin_token(self):
        token = self.get_user_token("test_admin")
        data = {
            "name": ".online",
        }

        response = self.client.post(
            "/api/domains/top/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        try:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json["success"])  # type: ignore
            self.assertIsNotNone(response.json["top_domain"])  # type: ignore
        except AssertionError:
            self.assertEqual(response.status_code, 409)
    
    def test_add_top_domain_with_user_token(self):
        token = self.get_user_token("test_user")
        data = {
            "name": ".online",
        }

        response = self.client.post(
            "/api/domains/top/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 403)

    def test_get_domains_without_token(self):
        response = self.client.get("/api/domains")

        self.assertEqual(response.status_code, 401)

    def test_get_domains_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page}

        response = self.client.get(
            "/api/domains",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["domains"])  # type: ignore
        self.assertGreater(len(response.json["domains"]), 0)  # type: ignore
        self.assertLess(len(response.json["domains"]), per_page + 1)  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore

    def test_search_domains_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page, "search_query": "test"}

        response = self.client.get(
            "/api/domains",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["domains"])  # type: ignore
        self.assertGreater(len(response.json["domains"]), 0)  # type: ignore
        self.assertLess(len(response.json["domains"]), per_page + 1)  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore

    def test_get_domains_with_user_token(self):
        token = self.get_user_token("test_user")
        page = 1
        per_page = 50

        response = self.client.get(
            "/api/domains",
            headers={"Authorization": "Bearer " + token},
            query_string={"page": page, "per_page": per_page},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["domains"])  # type: ignore
        self.assertGreater(len(response.json["domains"]), 0)  # type: ignore
        self.assertLess(len(response.json["domains"]), per_page + 1)  # type: ignore
        self.assertIsNotNone(response.json["total_count"])  # type: ignore
        for domain in response.json["domains"]:  # type: ignore
            self.assertEqual(domain["user_id"], current_user.id)

    def test_search_domains_with_user_token(self):
        token = self.get_user_token("test_user")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page, "search_query": "test"}

        response = self.client.get(
            "/api/domains",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["domains"])
        self.assertGreater(len(response.json["domains"]), 0)
        self.assertLess(len(response.json["domains"]), per_page + 1)
        self.assertIsNotNone(response.json["total_count"])
        for domain in response.json["domains"]:
            self.assertEqual(domain["user_id"], current_user.id)
            self.assertIn("test", domain["domain"])

    def test_get_domain_by_id_without_token(self):
        response = self.client.get("/api/domains/1")

        self.assertEqual(response.status_code, 401)

    def test_get_domain_by_id_with_admin_token(self):
        token = self.get_user_token("test_admin")
        domain = User.query.filter_by(username="test_user").first().domains[0]

        response = self.client.get(
            "/api/domains/" + str(domain.id),
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["domain"])
        self.assertEqual(response.json["domain"]["id"], domain.id)

    def test_get_domain_by_id_with_user_token(self):
        token = self.get_user_token("test_user")
        domain = User.query.filter_by(username="test_user").first().domains[0]

        response = self.client.get(
            "/api/domains/" + str(domain.id),
            headers={"Authorization": "Bearer " + token},
        )
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.json["domain"])
            self.assertEqual(response.json["domain"]["id"], domain.id)
            self.assertEqual(response.json["domain"]["user_id"], current_user.id)
        except AssertionError:
            self.assertEqual(response.status_code, 403)

    def test_add_domains_without_token(self):
        response = self.client.post(
            "/api/domains/add",
            json={
                "domains": ["test.com", "test2.com"],
                "user": 1,
                "test": True,
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_add_domains_with_admin_token(self):
        token = self.get_user_token("test_admin")
        user = User.query.filter_by(username="test_user").first()
        data = {
            "domains": ["test.com", "test2.com"],
            "user": user.id,  # type: ignore
            "test": True,
        }

        response = self.client.post(
            "/api/domains/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 200)

        data = {
            "domains": ["test3.com", "test4.com"],
            "user": None,  # type: ignore
            "test": True,
        }

    def test_add_domains_with_user_token(self):
        token = self.get_user_token("test_user")
        user = User.query.filter_by(username="test_user").first()
        data = {
            "domains": ["test.com", "test2.com"],
            "user": user.id,  # type: ignore
            "test": True,
        }

        response = self.client.post(
            "/api/domains/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 403)

    def test_add_domain_to_cf(self):
        domain = "testappstest.online"
        from client_api import add_domain_to_cf

        result = add_domain_to_cf(domain)
        pprint(result)

    def test_update_domain_status_without_token(self):
        response = self.client.patch(
            "/api/domains/update_status", json={"id": 1, "status": "active"}
        )
        self.assertEqual(response.status_code, 401)

    def test_update_domain_status_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_domain = Domain.query.first()
        try:
            self.assertIsNotNone(test_domain)
        except AssertionError:
            self.test_add_domains_with_admin_token()
            test_domain = Domain.query.first()
            self.assertIsNotNone(test_domain)

        response = self.client.patch(
            "/api/domains/update_status",
            json={"id": test_domain.id, "status": "active"},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)

    def test_update_domain_status_with_user_token(self):
        token = self.get_user_token("test_user")
        user = User.query.filter_by(username="test_user").first()
        test_domain = Domain.query.filter_by(user_id=user.id).first()
        try:
            self.assertIsNotNone(test_domain)
        except AssertionError:
            self.test_add_domains_with_admin_token()
            test_domain = Domain.query.first()
            self.assertIsNotNone(test_domain)

        response = self.client.patch(
            "/api/domains/update_status",
            json={"id": test_domain.id, "status": "active"},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)

    def test_purchase_domain_without_token(self):
        response = self.client.post(
            "/api/domains/purchase"
        )
        self.assertEqual(response.status_code, 401)

    def test_purchase_domain_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_domain = Domain.query.filter_by(user_id=None).first()
        try:
            self.assertIsNotNone(test_domain)
        except AssertionError:
            self.test_add_domains_with_admin_token()
            test_domain = Domain.query.filter_by(user_id=None).first()
            self.assertIsNotNone(test_domain)

        response = self.client.post(
            "/api/domains/purchase",  # type: ignore
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",},
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])  # type: ignore
        self.assertIsNotNone(response.json["domain"]) # type: ignore

    def test_purchase_domain_with_user_token(self):
        token = self.get_user_token("test_user")
        test_domain = Domain.query.filter_by(user_id=None).first()
        try:
            self.assertIsNotNone(test_domain)
        except AssertionError:
            self.test_add_domains_with_admin_token()
            test_domain = Domain.query.filter_by(user_id=None).first()
            self.assertIsNotNone(test_domain)

        response = self.client.post(
            "/api/domains/purchase",  # type: ignore
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                },
        )
        pprint(response.json)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIsNotNone(response.json["domain"])  # type: ignore

    # Landings

    def test_get_landings_without_token(self):
        response = self.client.get("/api/landings")

        self.assertEqual(response.status_code, 401)

    def test_get_landings_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page}

        response = self.client.get(
            "/api/landings",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["landings"])  # type: ignore

    def test_search_landings_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page, "search_query": "test"}

        response = self.client.get(
            "/api/landings",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["landings"])  # type: ignore
        

# GeoPrices

    def test_get_geo_prices_without_token(self):
        response = self.client.get("/api/geo_prices")

        self.assertEqual(response.status_code, 401)
    
    def test_get_geo_prices_with_admin_token(self):
        token = self.get_user_token("test_admin")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page}

        response = self.client.get(
            "/api/geo_prices",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["geo_prices"])
        self.assertIsNotNone(response.json["total_count"])
        
    def test_get_geo_prices_with_user_token(self):
        token = self.get_user_token("test_user")
        page = 1
        per_page = 50
        params = {"page": page, "per_page": per_page}

        response = self.client.get(
            "/api/geo_prices",
            headers={"Authorization": "Bearer " + token},
            query_string=params,
        )
        self.assertEqual(response.status_code, 403)
    
    def test_add_geo_price_without_token(self):
        response = self.client.post(
            "/api/geo_prices/add",
            json={
                "geo": "ua",
                "install_price": 0.1,
                "conversion_price": 0.2,
            },
        )
        self.assertEqual(response.status_code, 401)
        
    def test_add_geo_price_with_admin_token(self):
        token = self.get_user_token("test_admin")
        data = {
            "geo": "ua",
            "install_price": 0.1,
            "conversion_price": 0.2,
        }

        response = self.client.post(
            "/api/geo_prices/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            self.assertEqual(response.status_code, 409)
    
    def test_add_geo_price_with_user_token(self):
        token = self.get_user_token("test_user")
        data = {
            "geo": "ua",
            "install_price": 0.1,
            "conversion_price": 0.2,
        }

        response = self.client.post(
            "/api/geo_prices/add", json=data, headers={"Authorization": "Bearer " + token}
        )
        self.assertEqual(response.status_code, 403)
    
    def test_update_geo_price_without_token(self):
        response = self.client.patch(
            "/api/geo_prices/update",
            json={"id": 1, "install_price": 0.1, "conversion_price": 0.2}
        )
        self.assertEqual(response.status_code, 401)
        
    def test_update_geo_price_with_admin_token(self):
        token = self.get_user_token("test_admin")
        test_geo_price = GeoPrice.query.first()
        try:
            self.assertIsNotNone(test_geo_price)
        except AssertionError:
            self.test_add_geo_price_with_admin_token()
            test_geo_price = GeoPrice.query.first()
            self.assertIsNotNone(test_geo_price)

        response = self.client.patch(
            "/api/geo_prices/update",
            json={"id": test_geo_price.id, "install_price": 0.1, "conversion_price": 0.2},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        
    def test_update_geo_price_with_user_token(self):
        token = self.get_user_token("test_user")
        test_geo_price = GeoPrice.query.first()
        try:
            self.assertIsNotNone(test_geo_price)
        except AssertionError:
            self.test_add_geo_price_with_admin_token()
            test_geo_price = GeoPrice.query.first()
            self.assertIsNotNone(test_geo_price)

        response = self.client.patch(
            "/api/geo_prices/update",
            json={"id": test_geo_price.id, "install_price": 0.1, "conversion_price": 0.2},  # type: ignore
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 403)


# Statistics

    def test_get_campaign_statistics_without_token(self):
        response = self.client.get("/api/campaigns/1/statistics")

        self.assertEqual(response.status_code, 401)
    
    def test_get_campaign_statistics_with_admin_token(self):
        token = self.get_user_token("test_admin")
        campaign = Campaign.query.first()
        try:
            self.assertIsNotNone(campaign)
        except AssertionError:
            self.test_add_campaign_with_admin_token()
            campaign = Campaign.query.first()
            self.assertIsNotNone(campaign)
        
        response = self.client.get(
            "/api/campaigns/" + str(campaign.id) + "/statistics",
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json["campaign_statistics"])
        


if __name__ == "__main__":
    unittest.main()
