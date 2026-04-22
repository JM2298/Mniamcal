from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class ApiBaseUrlPageNumberPagination(PageNumberPagination):
	def _replace_base_url(self, link):
		if not link:
			return link

		api_server_url = getattr(settings, 'API_SERVER_URL', '').rstrip('/')
		if not api_server_url:
			return link

		target = urlsplit(link)
		base = urlsplit(api_server_url)
		return urlunsplit((base.scheme, base.netloc, target.path, target.query, target.fragment))

	def get_next_link(self):
		return self._replace_base_url(super().get_next_link())

	def get_previous_link(self):
		return self._replace_base_url(super().get_previous_link())