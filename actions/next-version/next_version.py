"""
Work out the next semantic version from git tags and PR labels.

The last release is the X.Y.Z tag (legacy X.Y.Z-RN tags count too) nearest to HEAD
in its history. Every PR merged since then must carry one of the labels
major/minor/patch; the highest one decides the bump. Commits that did not come in
through a PR count as a patch.

Nothing is written back to the repository: the version only exists in the build
(-Drevision/-Dchangelist) and, for releases, in the tag the workflow pushes.

Usage: next_version.py <dev|release> <prs.json>
  prs.json is the output of
  gh pr list --state merged --json number,title,labels,mergeCommit
"""
import json
import os
import re
import subprocess
import sys

BUMPS = ('patch', 'minor', 'major')  # ascending
RELEASE_TAG = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-R(\d+))?$')


def git(*args):
    return subprocess.run(('git',) + args, check=True, capture_output=True, text=True).stdout


def last_release():
    """The release tag nearest to HEAD in its history, or None.

    Nearest rather than highest, so a stale tag from an older numbering scheme deep in
    the history can't outrank the real last release.
    """
    best = None
    for tag in git('tag', '--merged', 'HEAD').split():
        m = RELEASE_TAG.match(tag)
        if not m:
            continue
        distance = int(git('rev-list', '--count', f'{tag}..HEAD'))
        version = tuple(int(g or 0) for g in m.groups())
        key = (-distance, version)
        if best is None or key > best[0]:
            best = (key, version, tag)
    return best and (best[1], best[2])


def pr_bump(pr):
    labels = {label['name'].lower() for label in pr.get('labels', [])}
    found = [b for b in BUMPS if b in labels]
    return found[-1] if found else None


def bump_version(base, bump):
    major, minor, patch = base
    if bump == 'major':
        return major + 1, 0, 0
    if bump == 'minor':
        return major, minor + 1, 0
    return major, minor, patch + 1


def output(**values):
    path = os.environ.get('GITHUB_OUTPUT')
    lines = [f'{k}={v}' for k, v in values.items()]
    print('\n'.join(lines))
    if path:
        with open(path, 'a') as f:
            f.write('\n'.join(lines) + '\n')


def summary(text):
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        with open(path, 'a') as f:
            f.write(text + '\n')


def main(mode, prs_path):
    if mode not in ('dev', 'release'):
        sys.exit(f'mode must be dev or release, got {mode!r}')

    release = last_release()
    if release:
        base, previous_tag = release[0][:3], release[1]
        commits = set(git('rev-list', f'{previous_tag}..HEAD').split())
    else:
        base, previous_tag = (0, 0, 0), ''
        commits = set(git('rev-list', 'HEAD').split())

    with open(prs_path) as f:
        prs = [pr for pr in json.load(f) if (pr.get('mergeCommit') or {}).get('oid') in commits]
    prs.sort(key=lambda pr: pr['number'])

    bump = 'patch'
    rows = []
    for pr in prs:
        pr_level = pr_bump(pr)
        if pr_level is None:
            print(f'::warning::PR #{pr["number"]} has no major/minor/patch label; counting it as a patch')
        elif BUMPS.index(pr_level) > BUMPS.index(bump):
            bump = pr_level
        rows.append(f'| #{pr["number"]} | {pr_level or "patch (unlabeled)"} | {pr["title"]} |')

    release_version = '.'.join(map(str, bump_version(base, bump)))
    if subprocess.run(['git', 'rev-parse', '-q', '--verify', f'refs/tags/{release_version}'],
                      capture_output=True).returncode == 0:
        sys.exit(f'Tag {release_version} already exists (left over from an older numbering scheme?); '
                 f'refusing to reuse it. Delete or rename the stale tag.')

    version = release_version + ('-SNAPSHOT' if mode == 'dev' else '')
    output(version=version,
           release_version=release_version,
           revision=release_version,
           changelist='-SNAPSHOT' if mode == 'dev' else '',
           previous_tag=previous_tag,
           bump=bump,
           has_changes=str(bool(commits)).lower())

    summary(f'### {version}\n\n'
            f'Last release: `{previous_tag or "none"}` · {len(commits)} commit(s) since · '
            f'bump: **{bump}**\n')
    if rows:
        summary('| PR | Label | Title |\n|---|---|---|\n' + '\n'.join(rows))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
