import os
import re
import requests
import simplejson as json
import sys

is_dev = os.environ.get('IS_DEV', 'false').lower() == 'true'
log_file = os.environ.get('LOG_FILE', 'log.txt')
artifact_filter = os.environ.get('ARTIFACT_FILTER', '.*?')
webhook_urls = [u.strip() for u in os.environ.get('WEBHOOK_URLS', '').splitlines() if u.strip()]
build_name = os.environ.get('BUILD_NAME', '')
commit = os.environ.get('COMMIT', '')
release_url = os.environ.get('RELEASE_URL', '')
repository = os.environ.get('GITHUB_REPOSITORY', '')

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
if build_name:
    version = name + '-' + build_name
elif is_dev:
    # Snapshot jars are named <artifact>-<version>-<yyyyMMdd.HHmmss>-<build>; show -SNAPSHOT instead
    version = re.sub(r'-\d{8}\.\d{6}-\d+$', '-SNAPSHOT', version)
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
    'url': release_url or url,
    'color': 5341129
}

if commit and repository:
    embed['description'] += f'\nCommit: [`{commit[:7]}`](https://github.com/{repository}/commit/{commit})'

for webhook_url in webhook_urls:
    requests.post(webhook_url,
                  headers={'Content-Type': 'application/json'},
                  data=json.dumps({'embeds': [embed]})
                  )
