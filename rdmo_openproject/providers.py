import hmac
import json
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from rdmo.projects.providers import OauthIssueProvider

from .mixins import OpenProjectProviderMixin


class OpenProjectIssueProvider(OpenProjectProviderMixin, OauthIssueProvider):
    add_label = _('Add OpenProject integration')
    send_label = _('Send to OpenProject')

    status_map = {
        'New': 'open',
        'To be scheduled': 'in_progress',
        'Scheduled': 'in_progress',
        'In progress': 'in_progress',
        'Closed': 'closed',
        'On hold': 'in_progress',
        'Rejected': 'closed'
    }

    @property
    def description(self):
        return _(f'This integration allow the creation of issues on {self.openproject_url}.')

    def send_issue(self, request, issue, integration, subject, message, attachments):
        self.store_in_session(request, 'issue_id', issue.id)
        self.store_in_session(request, 'integration_id', integration.id)
        self.store_in_session(request, 'project_url', integration.get_option_value('project_url'))
        self.store_in_session(request, 'work_package_type', integration.get_option_value('work_package_type'))
        self.store_in_session(request, 'subject', subject)
        self.store_in_session(request, 'message', message)
        self.store_in_session(request, 'attachments', attachments)

        return self.get_project_id(request)

    def get_project_id(self, request):
        project_url = self.pop_from_session(request, 'project_url')
        project_name = project_url.replace(f'{self.openproject_url}/projects', '').strip('/')
        query = quote(json.dumps([{
            'name_and_identifier': {
                'operator': '=',
                'values': [project_name]
            }
        }]))
        url = f'{self.api_url}/projects?filters={query}'

        return self.get(request, url)

    def get_type_id(self, request):
        url = f'{self.api_url}/types'
        return self.get(request, url)

    def post_issue(self, request):
        project_id = self.get_from_session(request, 'project_id')
        type_id = self.get_from_session(request, 'type_id')
        url = f'{self.api_url}/projects/{project_id}/work_packages'
        data = {
            '_links': {
                'type': {
                    'href': f'/api/v3/types/{type_id}'
                }
            },
            'subject': self.pop_from_session(request, 'subject'),
            'description': {
                'format': 'plain',
                'raw': self.pop_from_session(request, 'message'),
            }
        }

        return self.post(request, url, data)

    def post_attachment(self, request):
        work_package_id = self.get_from_session(request, 'work_package_id')
        attachments = self.pop_from_session(request, 'attachments')

        if attachments:
            file_name, file_content, file_type = attachments[0]
            url = f'{self.api_url}/work_packages/{work_package_id}/attachments'
            multipart = {
                'metadata': json.dumps({'fileName': file_name }),
                'file': (file_name, file_content, file_type)
            }

            self.store_in_session(request, 'attachments', attachments[1:])
            return self.post(request, url, multipart=multipart)

        else:
            # there are no attachments left, get the url of the work_package
            remote_url = self.get_work_package_url(work_package_id)

            # update the issue in rdmo
            self.update_issue(request, remote_url)

            # redirect to the work package in open project
            return HttpResponseRedirect(remote_url)

    def get_success(self, request, response):
        if '/projects' in response.url:
            try:
                project_id = response.json()['_embedded']['elements'][0]['id']
                self.store_in_session(request, 'project_id', project_id)
                return self.get_type_id(request)

            except (KeyError, IndexError):
                return render(request, 'core/error.html', {
                    'title': _('Integration error'),
                    'errors': [_('OpenProject project could not be found.')]
                }, status=200)

        elif '/types' in response.url:
            try:
                work_package_type = self.pop_from_session(request, 'work_package_type')
                for element in response.json()['_embedded']['elements']:
                    if element['name'] == work_package_type:
                        self.store_in_session(request, 'type_id', element['id'])
                        return self.post_issue(request)

            except KeyError:
                pass

            return render(request, 'core/error.html', {
                'title': _('Integration error'),
                'errors': [_('OpenProject work package type could not be found.')]
            }, status=200)

        elif response.request.method == 'POST':
            pass

        # return an error if everything failed
        return render(request, 'core/error.html', {
            'title': _('Integration error'),
            'errors': [_('The Integration is not configured correctly.')]
        }, status=200)

    def post_success(self, request, response):
        if '/projects/' in response.url:
            # get the upstream url of the issue
            work_package_id = response.json()['id']
            self.store_in_session(request, 'work_package_id', work_package_id)

        # post the next attachment
        return self.post_attachment(request)

    def get_work_package_url(self, work_package_id):
        return f'{self.openproject_url}/work_packages/{work_package_id}'

    def webhook(self, request, integration):
        secret = integration.get_option_value('secret')
        header_signature = request.headers.get('X-Op-Signature')

        if (secret is not None) and (header_signature is not None):
            body_signature = 'sha1=' + hmac.new(secret.encode(), request.body, 'sha1').hexdigest()

            if hmac.compare_digest(header_signature, body_signature):
                try:
                    payload = json.loads(request.body.decode())
                    action = payload.get('action')
                    work_package = payload.get('work_package')

                    if action and work_package:
                        work_package_id = work_package.get('id')
                        work_package_url = self.get_work_package_url(work_package_id)
                        work_package_status = work_package.get('_links', {}).get('status', {}).get('title')

                        try:
                            issue_resource = integration.resources.get(url=work_package_url)
                            status_map = self.status_map
                            status_map.update(settings.OPENPROJECT_PROVIDER.get('status_map', {}))

                            if work_package_status in status_map:
                                issue_resource.issue.status = status_map[work_package_status]
                                issue_resource.issue.save()

                        except ObjectDoesNotExist:
                            pass

                    return HttpResponse(status=200)

                except json.decoder.JSONDecodeError as e:
                    return HttpResponse(e, status=400)

        raise Http404

    @property
    def fields(self):
        return [
            {
                'key': 'project_url',
                'placeholder': f'{self.openproject_url}/projects/<name>',
                'help': _('The URL of the OpenProject project to send tasks to.')
            },
            {
                'key': 'work_package_type',
                'placeholder': 'Work Package Type',
                'help': _('The type of workpackage to create, e.g. "Task"')
            },
            {
                'key': 'secret',
                'placeholder': 'Secret (random) string',
                'help': _('The secret for a OpenProject webhook to close a task (optional).'),
                'required': False,
                'secret': True
            }
        ]
