import os
import re
import requests
import simplejson as json
import sys

is_dev = os.environ.get('IS_DEV', 'false').lower() == 'true'
log_file = os.environ.get('LOG_FILE', 'log.txt')
artifact_filter = os.environ.get('ARTIFACT_FILTER', '.*?')
webhook_urls = [u.strip() for u in os.environ.get('WEBHOOK_URLS', '').splitlines() if u.strip()]

search_string = (
    r'Uploaded to (magemonkey-repo): (https:\/\/repo\.travja\.dev(:443)?\/.*?\/studio\/magemonkey\/('
    + artifact_filter
    + r')\/(.*?)\/(.*?)(?<!sources|javadoc)\.jar(?!\.asc)) '
)

def get_info():
    with open(log_file, 'r') as file:
        content = file.read()
        content = re.sub(r'\x1B\[([0-9]{1,3}(;[0-9]{1,2};?)?)?[mGK]', '', content)  # Remove ANSI escape codes
        data = re.findall(search_string, content, re.MULTILINE)
        print(data)
        found_version = data[-1][5]
        artifact_id = data[-1][3]
        artifact_url = data[-1][1]
        return found_version, artifact_id, artifact_url


version, name, url = get_info()
if is_dev:
    split = version.split('-')[0:-2]
    version = '-'.join(split)
embed = {
    'username': 'Dev Mage',
    'author': {
        'name': 'New ' + ('Dev ' if is_dev else '') + 'Build Available!',
        'url': 'https://github.com/magemonkeystudio/' + name
    },
    'image': {
        'url': 'https://fabled.magemonkey.studio/' + ('dev_build.gif' if is_dev else 'release_build.gif')
    },
    'title': version,
    'description': 'Click the link above to download the new build!',
    'url': url,
    'color': 5341129
}

for webhook_url in webhook_urls:
    requests.post(webhook_url,
                  headers={'Content-Type': 'application/json'},
                  data=json.dumps({'embeds': [embed]})
                  )
