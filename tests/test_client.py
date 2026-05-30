"""Unit tests for the FatSecret client — all run against recorded fixtures (no live calls)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fatsecret.models import (
    FoodCandidate,
    normalize_recognition_response,
    normalize_search_response,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestNormalizeRecognition(unittest.TestCase):
    def test_single_food(self):
        data = _load("recognition_single.json")
        candidates = normalize_recognition_response(data)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.food_id, "33722")
        self.assertEqual(c.food_name, "Margherita Pizza")
        self.assertIsNone(c.brand)
        self.assertEqual(len(c.servings), 1)
        s = c.servings[0]
        self.assertEqual(s.serving_id, "157886")
        self.assertAlmostEqual(s.calories, 272.0)
        self.assertAlmostEqual(s.protein, 12.4)
        self.assertAlmostEqual(s.carbohydrate, 33.6)
        self.assertAlmostEqual(s.fat, 9.8)
        self.assertAlmostEqual(s.sodium, 551.0)

    def test_multi_food(self):
        data = _load("recognition_multi.json")
        candidates = normalize_recognition_response(data)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].food_name, "Margherita Pizza")
        self.assertEqual(candidates[1].food_name, "Caesar Salad")
        self.assertAlmostEqual(candidates[1].servings[0].calories, 481.0)

    def test_empty_response(self):
        data = _load("recognition_empty.json")
        candidates = normalize_recognition_response(data)
        self.assertEqual(candidates, [])

    def test_error_211_no_food_response_key(self):
        data = _load("recognition_error_211.json")
        # error responses have no food_response key
        candidates = normalize_recognition_response(data)
        self.assertEqual(candidates, [])

    def test_to_dict_round_trip(self):
        data = _load("recognition_single.json")
        candidates = normalize_recognition_response(data)
        d = candidates[0].to_dict()
        self.assertIn("food_id", d)
        self.assertIn("servings", d)
        self.assertIsInstance(d["servings"], list)
        serving_d = d["servings"][0]
        self.assertIn("calories", serving_d)
        self.assertIn("protein_g", serving_d)


class TestNormalizeSearch(unittest.TestCase):
    def test_multiple_results(self):
        data = _load("search_results.json")
        candidates = normalize_search_response(data)
        self.assertEqual(len(candidates), 2)
        c = candidates[0]
        self.assertEqual(c.food_id, "33722")
        self.assertEqual(c.brand, "Trader Joe's")
        self.assertEqual(len(c.servings), 2)
        self.assertAlmostEqual(c.servings[0].calories, 272.0)
        self.assertAlmostEqual(c.servings[1].calories, 1120.0)
        self.assertAlmostEqual(c.servings[0].metric_amount, 107.0)
        self.assertEqual(c.servings[0].metric_unit, "g")

    def test_single_serving_as_dict(self):
        # serving returned as dict (not list) when only one — both shapes tested
        data = _load("search_results.json")
        candidates = normalize_search_response(data)
        c = candidates[1]  # Generic pizza has serving as a dict in fixture
        self.assertEqual(len(c.servings), 1)
        self.assertEqual(c.servings[0].serving_id, "77441")

    def test_empty_search(self):
        data: dict = {"foods": {}}
        candidates = normalize_search_response(data)
        self.assertEqual(candidates, [])


class TestClientImageRecognition(unittest.TestCase):
    """Test FatSecretClient.image_recognition against a fixture response."""

    def _make_client(self):
        from fatsecret.auth import OAuth1Signer, OAuth2TokenManager
        from fatsecret.client import FatSecretClient

        oauth2 = MagicMock(spec=OAuth2TokenManager)
        oauth2.auth_header.return_value = {"Authorization": "Bearer test"}
        oauth1 = MagicMock(spec=OAuth1Signer)
        oauth1.auth = MagicMock()
        return FatSecretClient(oauth2=oauth2, oauth1=oauth1)

    @patch("fatsecret.client._load_and_encode_image", return_value="base64data")
    def test_recognition_returns_candidates(self, _mock_encode):
        client = self._make_client()
        fixture = _load("recognition_single.json")

        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_resp.raise_for_status = MagicMock()
        client._session.post = MagicMock(return_value=mock_resp)

        candidates = client.image_recognition("/tmp/photo.jpg")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].food_id, "33722")

    @patch("fatsecret.client._load_and_encode_image", return_value="base64data")
    def test_recognition_multi(self, _mock_encode):
        client = self._make_client()
        fixture = _load("recognition_multi.json")

        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_resp.raise_for_status = MagicMock()
        client._session.post = MagicMock(return_value=mock_resp)

        candidates = client.image_recognition("/tmp/photo.jpg")
        self.assertEqual(len(candidates), 2)


class TestClientFoodEntry(unittest.TestCase):
    def _make_client(self):
        from fatsecret.auth import OAuth1Signer, OAuth2TokenManager
        from fatsecret.client import FatSecretClient

        oauth2 = MagicMock(spec=OAuth2TokenManager)
        oauth2.auth_header.return_value = {"Authorization": "Bearer test"}
        oauth1 = MagicMock(spec=OAuth1Signer)
        oauth1.auth = MagicMock()
        return FatSecretClient(oauth2=oauth2, oauth1=oauth1)

    def test_create_food_entry_success(self):
        from datetime import date

        client = self._make_client()
        fixture = _load("food_entry_created.json")

        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_resp.raise_for_status = MagicMock()
        client._session.post = MagicMock(return_value=mock_resp)

        result = client.create_food_entry(
            food_id="33722",
            serving_id="157886",
            number_of_units=1.0,
            meal="dinner",
            food_entry_name="Margherita Pizza, 1 slice",
            entry_date=date(2026, 5, 29),
        )
        self.assertEqual(result.status, "logged")
        self.assertEqual(result.food_entry_id, "99482145")
        self.assertEqual(result.meal, "dinner")
        self.assertAlmostEqual(result.calories, 272.0)


if __name__ == "__main__":
    unittest.main()
