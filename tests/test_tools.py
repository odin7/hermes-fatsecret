"""Unit tests for tool handlers — mock the FatSecret client."""
from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fatsecret.models import FoodCandidate, LogResult, Serving


def _make_candidate(food_id="33722", food_name="Margherita Pizza", calories=272.0):
    serving = Serving(
        serving_id="157886",
        description="1 slice (107g)",
        calories=calories,
        protein=12.4,
        carbohydrate=33.6,
        fat=9.8,
    )
    return FoodCandidate(food_id=food_id, food_name=food_name, brand=None, servings=[serving])


def _make_log_result():
    return LogResult(
        status="logged",
        food_entry_id="99482145",
        logged_food_name="Margherita Pizza, 1 slice",
        meal="dinner",
        date="2026-05-29",
        calories=272.0,
    )


class TestAnalyzeFoodPhoto(unittest.TestCase):
    @patch("tools._client")
    def test_returns_candidates(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.image_recognition.return_value = [_make_candidate()]
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.analyze_food_photo({"image_path": "/tmp/photo.jpg"}))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["food_id"], "33722")

    @patch("tools._client")
    def test_no_image_returns_error(self, _mock):
        import tools
        result = json.loads(tools.analyze_food_photo({}))
        self.assertIn("error", result)

    @patch("tools._client")
    def test_empty_recognition_returns_no_food(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.image_recognition.return_value = []
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.analyze_food_photo({"image_path": "/tmp/photo.jpg"}))
        self.assertEqual(result["status"], "no_food_detected")

    @patch("tools._client")
    def test_http_error_211_handled(self, mock_client_fn):
        import requests

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": {"code": "211", "message": "No food item detected"}}
        http_err = requests.HTTPError(response=mock_resp)
        mock_client.image_recognition.side_effect = http_err
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.analyze_food_photo({"image_path": "/tmp/photo.jpg"}))
        self.assertEqual(result["status"], "no_food_detected")
        self.assertIn("211", result["message"])

    @patch("tools._client")
    def test_kwargs_attachment_fallback(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.image_recognition.return_value = [_make_candidate()]
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.analyze_food_photo(
            {},
            attachment_paths=["/tmp/gateway_photo.jpg"],
        ))
        self.assertEqual(result["status"], "ok")
        mock_client.image_recognition.assert_called_once_with(
            "/tmp/gateway_photo.jpg", region="US", language="en"
        )


class TestAnalyzeFoodPhotoHermesBackend(unittest.TestCase):
    def setUp(self):
        import os
        os.environ["FATSECRET_RECOGNITION_BACKEND"] = "hermes"

    def tearDown(self):
        import os
        os.environ.pop("FATSECRET_RECOGNITION_BACKEND", None)

    @patch("tools._client")
    def test_hermes_backend_uses_search(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.search_foods.return_value = [_make_candidate()]
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.analyze_food_photo({
            "image_path": "/tmp/photo.jpg",
            "description": "a bowl of oatmeal with blueberries",
        }))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "hermes")
        mock_client.search_foods.assert_called_once()
        mock_client.image_recognition.assert_not_called()

    @patch("tools._client")
    def test_hermes_backend_missing_description_returns_error(self, _mock):
        import tools
        result = json.loads(tools.analyze_food_photo({"image_path": "/tmp/photo.jpg"}))
        self.assertIn("error", result)
        self.assertIn("hermes", result["error"].lower())

    @patch("tools._client")
    def test_hermes_backend_no_results(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.search_foods.return_value = []
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.analyze_food_photo({
            "image_path": "/tmp/photo.jpg",
            "description": "xyzzy unrecognizable dish",
        }))
        self.assertEqual(result["status"], "no_results")

    @patch("tools._client")
    def test_fatsecret_backend_unchanged_with_env_unset(self, mock_client_fn):
        import os
        os.environ.pop("FATSECRET_RECOGNITION_BACKEND", None)

        mock_client = MagicMock()
        mock_client.image_recognition.return_value = [_make_candidate()]
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.analyze_food_photo({"image_path": "/tmp/photo.jpg"}))
        self.assertEqual(result["backend"], "fatsecret")
        mock_client.image_recognition.assert_called_once()
        mock_client.search_foods.assert_not_called()


class TestSearchFood(unittest.TestCase):
    @patch("tools._client")
    def test_returns_results(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.search_foods.return_value = [_make_candidate(), _make_candidate("99012", "Generic Pizza", 254.0)]
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.search_food({"query": "margherita pizza"}))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["candidates"]), 2)

    @patch("tools._client")
    def test_empty_query_returns_error(self, _mock):
        import tools
        result = json.loads(tools.search_food({"query": ""}))
        self.assertIn("error", result)

    @patch("tools._client")
    def test_no_results(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.search_foods.return_value = []
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.search_food({"query": "xyzzynotafood"}))
        self.assertEqual(result["status"], "no_results")


class TestLogFoodEntry(unittest.TestCase):
    def setUp(self):
        # Clear idempotency state between tests
        import tools
        tools._logged_this_session.clear()

    @patch("tools._client")
    def test_logs_successfully(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.create_food_entry.return_value = _make_log_result()
        mock_client_fn.return_value = mock_client

        import tools
        result = json.loads(tools.log_food_entry({
            "food_id": "33722",
            "serving_id": "157886",
            "quantity": 1,
            "meal": "dinner",
            "food_entry_name": "Margherita Pizza, 1 slice",
            "date": "2026-05-29",
        }))
        self.assertEqual(result["status"], "logged")
        self.assertEqual(result["food_entry_id"], "99482145")
        self.assertAlmostEqual(result["calories"], 272.0)

    @patch("tools._client")
    def test_missing_food_id_returns_error(self, _mock):
        import tools
        result = json.loads(tools.log_food_entry({
            "serving_id": "157886",
            "quantity": 1,
            "meal": "dinner",
            "food_entry_name": "Pizza",
        }))
        self.assertIn("error", result)

    @patch("tools._client")
    def test_idempotency_blocks_duplicate(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.create_food_entry.return_value = _make_log_result()
        mock_client_fn.return_value = mock_client

        import tools
        args = {
            "food_id": "33722",
            "serving_id": "157886",
            "quantity": 1,
            "meal": "dinner",
            "food_entry_name": "Margherita Pizza, 1 slice",
            "date": "2026-05-29",
        }
        tools.log_food_entry(args)  # first call
        result = json.loads(tools.log_food_entry(args))  # duplicate
        self.assertEqual(result["status"], "duplicate_skipped")
        self.assertEqual(mock_client.create_food_entry.call_count, 1)

    @patch("tools._client")
    def test_invalid_date_returns_error(self, _mock):
        import tools
        result = json.loads(tools.log_food_entry({
            "food_id": "33722",
            "serving_id": "157886",
            "quantity": 1,
            "meal": "dinner",
            "food_entry_name": "Pizza",
            "date": "not-a-date",
        }))
        self.assertIn("error", result)

    @patch("tools._client")
    def test_invalid_meal_falls_back_to_default(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.create_food_entry.return_value = _make_log_result()
        mock_client_fn.return_value = mock_client

        import tools
        tools.log_food_entry({
            "food_id": "33722",
            "serving_id": "157886",
            "quantity": 1,
            "meal": "snack",  # not a valid meal type
            "food_entry_name": "Pizza",
        })
        call_kwargs = mock_client.create_food_entry.call_args
        self.assertIn(call_kwargs.kwargs["meal"], {"breakfast", "lunch", "dinner", "other"})


if __name__ == "__main__":
    unittest.main()
