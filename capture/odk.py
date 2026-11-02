import requests


class CentralClient:
    """Minimal ODK Central API client for reading submissions."""
    PAGE_SIZE = 500

    def __init__(self, url, email, password, project_id, verify_tls=True):
        self.url = url.rstrip('/')
        self.project_id = project_id
        self.session = requests.Session()
        self.session.verify = verify_tls
        response = self.session.post(
            f'{self.url}/v1/sessions', json={'email': email, 'password': password}, timeout=30
        )
        response.raise_for_status()
        self.session.headers['Authorization'] = f"Bearer {response.json()['token']}"

    def submissions(self, xml_form_id):
        """Yield every submission record for a form, one page at a time."""
        endpoint = f'{self.url}/v1/projects/{self.project_id}/forms/{xml_form_id}.svc/Submissions'
        skip = 0
        while True:
            response = self.session.get(
                endpoint, params={'$top': self.PAGE_SIZE, '$skip': skip}, timeout=60
            )
            response.raise_for_status()
            records = response.json()['value']
            yield from records
            if len(records) < self.PAGE_SIZE:
                return
            skip += self.PAGE_SIZE
