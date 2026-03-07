import os
import re
import sys

is_dev = len(sys.argv) >= 2 and sys.argv[1].strip().lower() in ('true', '1')
prep   = not is_dev and len(sys.argv) >= 3 and bool(sys.argv[2].strip())

artifact_filter = os.environ.get('ARTIFACT_FILTER', '').strip()
use_anchor = artifact_filter and artifact_filter != '.*?'

# Named-group version pattern (shared by both regex variants)
_VER = (
    r'(?P<full>'
      r'(?P<bare>(?:\d+\.?)+)'
      r'(?P<r_full>-R(?P<r_num>\d+)\.?(?P<patch>\d+)?)?'
      r'(?P<snapshot>-SNAPSHOT)?'
    r')'
)

if use_anchor:
    # Codex-style: anchor on <artifactId> to avoid matching parent/dependency versions
    REGEX = re.compile(
        r'(?P<prefix><artifactId>.*' + re.escape(artifact_filter) + r'.*</artifactId>\s*)'
        r'<version>' + _VER + r'</version>',
        re.MULTILINE
    )
else:
    # Standard: match the 4-space-indented root <version> tag
    REGEX = re.compile(
        r'(?P<prefix>^    )<version>' + _VER + r'</version>$',
        re.MULTILINE
    )


def compute_new_version(m):
    version = m.group('full')
    bare    = m.group('bare')
    r_num   = m.group('r_num')
    patch   = m.group('patch')
    snapshot = m.group('snapshot')

    if is_dev:
        if r_num is None:
            return version + '-R0.1-SNAPSHOT'
        elif snapshot is None:
            return version + '.1-SNAPSHOT'
        else:
            new_patch = int(patch) + 1
            return bare + f'-R{r_num}.{new_patch}-SNAPSHOT'
    elif prep:
        new_r = (int(r_num) + 1) if r_num else 1
        return bare + f'-R{new_r}'
    else:
        # Increment the last numeric segment of bare version
        last_dot = bare.rfind('.')
        if last_dot >= 0:
            return bare[:last_dot + 1] + str(int(bare[last_dot + 1:]) + 1)
        return str(int(bare) + 1)


def replace_version(pom_path):
    with open(pom_path, 'r') as f:
        contents = f.read()
    m = REGEX.search(contents)
    if not m:
        return
    new_version = compute_new_version(m)
    prefix = m.group('prefix')
    replacement = prefix + '<version>' + new_version + '</version>'
    new_contents = REGEX.sub(replacement, contents, count=1)
    with open(pom_path, 'w') as f:
        f.write(new_contents)
    print(f'  {pom_path}: {m.group("full")} -> {new_version}')


def find_pom_files(directory):
    for root, _, files in os.walk(directory):
        for name in files:
            if name in ('pom.xml', 'pom-dev.xml'):
                path = os.path.join(root, name)
                if '-nms' not in path:
                    yield path


if __name__ == '__main__':
    for pom in find_pom_files(os.getcwd()):
        replace_version(pom)
