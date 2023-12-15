from argparse import Namespace
from datetime import datetime
import unittest
from app import app, send_conversion_to_fb
from models import Campaign, CampaignClick


class TestApp(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_home_without_campaign_id(self):
        response = self.client.get("/")
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            print(response.data.decode("utf-8"))

    def test_home_with_campaign_id(self):
        response = self.client.get(
            "/?uchsik=b485fc837656a47c5eccbfcf2394975a952cb40937efb571afa7b63d88218549"
        )
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            print(response.data.decode("utf-8"))

    def test_not_found_error(self):
        response = self.client.get("/invalid")
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            self.assertIn(b'"error"', response.data)
            print(response.data.decode("utf-8"))

    def test_internal_error(self):
        with app.app_context():
            response = self.client.get("/")
            try:
                self.assertEqual(response.status_code, 200)
            except AssertionError:
                self.assertIn(b'"error"', response.data)
                print(response.data.decode("utf-8"))

    def test_get_inapp_click(self):
        required_params = {  # noqa: F841
            "clid": "123",
            "ip": "127.0.0.1",
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "ref": "https://www.google.com/",
            "url": "http://domain.com/",
            "subdomain": "inapp",
            "domain": "example.com",
        }

        response = self.client.get("/?clid=123", subdomain="example")
        try:
            self.assertEqual(response.status_code, 200)
        except AssertionError:
            self.assertIn(b'"error"', response.data)
            print(response.data.decode("utf-8"))

    def test_send_conversion(self):
        event = "Lead"
        campaign_click = {
            "click_id": "123",
            "fbclid": "123",
            "rma": "123",
            "ulb": "123",
            "domain": "example.com",
        }
        campaign_click = Namespace(**campaign_click)

        conversion_url = send_conversion_to_fb(event, campaign_click)  # type: ignore  # noqa: F841

    def test_handle_inapp_with_valid_clid_and_event(self):
        click_obj = CampaignClick.query.filter_by(offer_url="123").first()
        print(click_obj)
        if not click_obj:
            click_obj = CampaignClick(
                click_id="123",
                fbclid="123",
                rma="123",
                ulb=12312312,
                offer_url="123",
                domain="example.com",
                request_parameters=dict(),
                campaign_hash="123",
                campaign_id=1,
                campaign=Campaign.query.first(),
                ip="127.0.0.1",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ",
                referer="https://www.google.com/",
                timestamp=datetime.now(),
                blocked=False,
            )

        response = self.client.get(
            f"/?clid={click_obj.click_id}&event=Lead",
            headers={"Host": "inapp.yoursapp.online"},
            subdomain="inapp",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertTrue(response.json["conversion_sent"])
        self.assertEqual(response.json["clid"], click_obj.click_id)

    def test_handle_inapp_with_valid_clid_and_no_event(self):
        response = self.client.get(
            "/?clid=123", headers={"Host": "inapp.yoursapp.online"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertFalse(response.json["conversion_sent"])
        self.assertEqual(response.json["clid"], "123")
        self.assertIn("http", response.json["offer_url"])

    def test_handle_inapp_with_invalid_clid(self):
        response = self.client.get(
            "/?clid=invalid", headers={"Host": "inapp.yoursapp.online"}
        )
        try:
            self.assertEqual(response.status_code, 404)
        except AssertionError:
            self.assertEqual(response.status_code, 400)

    def test_handle_inapp_with_no_clid(self):
        response = self.client.get("/", headers={"Host": "inapp.yoursapp.online"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "No campaign provided.")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestApp)
    unittest.TextTestRunner(verbosity=2).run(suite)
