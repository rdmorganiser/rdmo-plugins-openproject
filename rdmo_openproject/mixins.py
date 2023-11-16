from django.conf import settings
from django.urls import reverse

from rdmo.services.providers import OauthProviderMixin


class OpenProjectProviderMixin(OauthProviderMixin):

    @property
    def openproject_url(self):
        return settings.OPENPROJECT_PROVIDER['openproject_url'].strip('/')

    @property
    def authorize_url(self):
        return f'{self.openproject_url}/oauth/authorize'

    @property
    def token_url(self):
        return f'{self.openproject_url}/oauth/token'

    @property
    def api_url(self):
        return f'{self.openproject_url}/api/v3'

    @property
    def client_id(self):
        return settings.OPENPROJECT_PROVIDER['client_id']

    @property
    def client_secret(self):
        return settings.OPENPROJECT_PROVIDER['client_secret']

    @property
    def redirect_path(self):
        return reverse('oauth_callback', args=['openproject'])

    def get_authorize_params(self, request, state):
        return {
            'client_id': self.client_id,
            'redirect_uri': request.build_absolute_uri(self.redirect_path),
            'response_type': 'code',
            'scope': 'api_v3',
            'state': state
        }

    def get_callback_data(self, request):
        return {
            'token_url': self.token_url,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': request.GET.get('code'),
            'grant_type': 'authorization_code',
            'redirect_uri': request.build_absolute_uri(self.redirect_path)
        }

    def get_error_message(self, response):
        return response.json().get('message')
