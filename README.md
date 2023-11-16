rdmo-openproject
================

This plugin implements an [issue provider](https://rdmo.readthedocs.io/en/latest/plugins/index.html#issue-providers) for RDMO, which lets users push their tasks from RDMO to OpenProject work packages. The plugin uses [OAUTH 2.0](https://oauth.net/2/), so that users use their respective accounts in both systems.


Setup
-----

Install the plugin in your RDMO virtual environment using pip (directly from GitHub):

```bash
pip install git+https://github.com/rdmorganiser/rdmo-openproject
```

Add the plugin to `PROJECT_ISSUE_PROVIDERS` in `config/settings/local.py`:

```python
PROJECT_ISSUE_PROVIDERS += [
    ('openproject', _('OpenProject Provider'), 'rdmo_openproject.providers.OpenProject')
]
```

In addition, an “App” has to be registered with the particular OpenProject instance. Go to `/admin/oauth/applications` on your OpenProject instance and create a new application with the callback URL `https://<rdmo_url>/services/oauth/openproject/callback/` and the scope `api_v3`.

The `client_id` and the `client_secret`, together with the `openproject_url`, need to be configured in `config/settings/local.py`:

```python
OPENPROJECT_PROVIDER = {
    'openproject_url': ''
    'client_id': '',
    'client_secret': ''
}
```


Usage
-----

After the setup, users can add a OpenProject intergration to their projects. They need to provide the URL to the project and the type of work package, e.g. Task, Milestone. Afterwards, project tasks can be pushed to the OpenProject project.

Additionally, a secret can be added to enable OpenProject to communicate to RDMO when the status of a work package changed. For this, a webhook has to be added at `https://<openproject_url>/admin/settings/webhooks/new` (by an administrator). The webhook has to point to `https://<rdmo_url>/projects/<project_id>/integrations/<integration_id>/webhook/` and the signature secret has to be exactly the secret entered in the integration.
