from rest_framework import status
from rest_framework.test import APITestCase


class DietApiTests(APITestCase):
	diets_url = '/api/diets/'
	diet_meals_url = '/api/diets/meals/'
	diet_calories_url = '/api/diets/calories/'
	simplified_products_url = '/api/products/simplified/'

	def test_diets_endpoint_returns_paginated_result(self):
		response = self.client.get(self.diets_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('count', response.data)
		self.assertIn('next', response.data)
		self.assertIn('previous', response.data)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_diet_meals_endpoint_returns_paginated_result(self):
		response = self.client.get(self.diet_meals_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)
		if response.data['results']:
			self.assertIn('czysta_kalorycznosc_diety', response.data['results'][0])
			self.assertIn('skladniki', response.data['results'][0])
			self.assertIn('czy_oceniony', response.data['results'][0])
			self.assertIn('ocena_uzytkownika', response.data['results'][0])
			self.assertIn('ocena_uzytkownika_id', response.data['results'][0])

	def test_diet_meals_endpoint_accepts_dieta_id_filter(self):
		response = self.client.get(self.diet_meals_url, {'dieta-id': 1})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_diet_meals_endpoint_accepts_kalorycznosc_diety_id_filter(self):
		response = self.client.get(self.diet_meals_url, {'kalorycznosc-diety-id': 1})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_diet_meals_endpoint_accepts_kalorycznosc_id_filter(self):
		response = self.client.get(self.diet_meals_url, {'kalorycznosc-id': 1})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_diet_meals_endpoint_accepts_czysta_kalorycznosc_filter(self):
		response = self.client.get(self.diet_meals_url, {'czysta-kalorycznosc': 1800})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_diet_meals_endpoint_accepts_all_new_filters(self):
		response = self.client.get(
			self.diet_meals_url,
			{
				'dieta-id': 1,
				'pora-posilku': 'obiad',
				'nazwa-pospillku': 'makaron',
				'czas-przygotowania': '15',
				'czas-przygotowania-max-minut': 30,
				'sortowanie-cena': 'najtansze',
			},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_diet_meals_endpoint_accepts_price_sorting_filter(self):
		response = self.client.get(self.diet_meals_url, {'sortowanie-cena': 'najtansze'})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_diet_calories_endpoint_returns_paginated_result(self):
		response = self.client.get(self.diet_calories_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_simplified_products_endpoint_returns_paginated_result(self):
		response = self.client.get(self.simplified_products_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)

	def test_simplified_products_endpoint_accepts_filters(self):
		response = self.client.get(
			self.simplified_products_url,
			{
				'nazwa-produktu': 'ryz',
				'kategoria-id': 1,
			},
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		self.assertIsInstance(response.data['results'], list)
