# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from __future__ import print_function

import datetime
import fnmatch
import os
import shutil

import yaml
from invoke import task

from .common import (
    GIT_IGNORES,
    TEMPLATE_GIT,
    TEMPLATE_GIT_REPO_URL,
    ask_or_abort,
    build_path,
    cd,
    check_git_diff,
    cookiecutter_context,
    exit_msg,
    root_path,
    tempdir,
    update_yml_file,
)

try:
    from cookiecutter.main import cookiecutter
except ImportError:
    cookiecutter = None


SYNC_METADATA = build_path('.sync.yml')


def sync_meta():
    with open(SYNC_METADATA, 'rU') as f:
        return yaml.load(f.read())


def update_sync_meta(data):
    allowed_data = {
        k: v for k, v in data.items() if k in ('pinned_version', 'last_sync')
    }
    update_yml_file(SYNC_METADATA, allowed_data, main_key='sync')


def now():
    return datetime.datetime.now().strftime('%Y%m%d-%H%M')


def _exclude_fnmatch(root, files, exclude):
    return list(
        set(files)
        - {
            d
            for d in files
            for excl in exclude
            if fnmatch.fnmatch(os.path.join(root, d), excl)
        }
    )


def _add_comment_unknown(path, comment):
    print('No function to add a comment in {}'.format(path))


def _add_comment_py(path, comment):
    with open(path, 'rU') as f:
        content = f.readlines()
    insert_at = 0
    for index, line in enumerate(content):
        if line.startswith('#!'):
            insert_at = index + 1
        if 'coding:' in line:
            insert_at = index + 1
            break
    comment = '\n'.join(['# {}'.format(line) for line in comment.splitlines()])
    comment += '\n'
    content.insert(insert_at, comment)
    with open(path, 'w') as f:
        f.write(''.join(content))


def _add_comment_md(path, comment):
    with open(path, 'rU') as f:
        content = f.readlines()
    insert_at = 0
    comment = '<!--\n{}-->\n'.format(comment)
    content.insert(insert_at, comment)
    with open(path, 'w') as f:
        f.write(''.join(content))


def _add_comment_sh(path, comment):
    with open(path, 'rU') as f:
        content = f.readlines()
    insert_at = 0
    for index, line in enumerate(content):
        if line.startswith('#!'):
            insert_at = index + 1
    comment = '\n'.join(['# {}'.format(line) for line in comment.splitlines()])
    comment += '\n'
    content.insert(insert_at, comment)
    with open(path, 'w') as f:
        f.write(''.join(content))


def _add_comment_xml(path, comment):
    with open(path, 'rU') as f:
        content = f.readlines()
    insert_at = 0
    for index, line in enumerate(content):
        if line.startswith('<?xml version="1.0" encoding="utf-8"?>'):
            insert_at = index + 1
    comment = '<!--\n{}-->\n'.format(comment)
    content.insert(insert_at, comment)
    with open(path, 'w') as f:
        f.write(''.join(content))


def add_comment(path, comment):
    __, ext = os.path.splitext(path)
    if ext in ('.png', '.jpeg', '.jpg'):
        return
    funcs = {
        '.py': _add_comment_py,
        '.md': _add_comment_md,
        '.sh': _add_comment_sh,
        '.xml': _add_comment_xml,
    }
    if not ext:
        with open(path, 'rU') as f:
            line = f.readline()
            if line.startswith('#!'):
                if 'python' in line:
                    ext = '.py'
                if 'sh' in line:
                    ext = '.sh'

    funcs.get(ext, _add_comment_unknown)(path, comment)


def get_sync_version(version=None, pinned_version=None):
    """Retrieve version to be used for sync.

    :param version: desired custom version. Default: `stable`.
    :param pinned_version: version pinned from last sync session.

    Cases:

    1. If `version` is not provided and there's no `pinned_version`
       you'll get 'stable'.
    2. If `version` is not provided and`pinned_version` is valued
       you'll get the pinned one back.
    3. If `version` is provided you'll get it,
       no matter if the pinned one is there too.

    In any case you'll get a nice report on what's happening on versions.
    """
    sync_version = 'stable' if not pinned_version else pinned_version
    if pinned_version:
        print('Last pinned version is:', pinned_version)
    else:
        print('No former pinned version, default to:', sync_version)
    if version:
        print('Required version is:', version)
        sync_version = version
    print('Using:', sync_version)
    return sync_version


@task
def sync(ctx, commit=True, version=None, fork=None, fork_url=None):
    """Sync files from the project template.

    :param commit: commit changes after sync
    :param version: template version to sync. By default: `stable` branch.

        In case you want to use a specific branch or tag, just pass it as:

        --version=2.x.x.x

        If you know what you are doing you could use `dev` branch ;)

    :param fork: github fork project to pull from (ie: simahawk/odoo-template)
    :param fork_url: git repo full URL to pull from.
        Useful when you want to test a local fork w/ pushing anything.
    """
    if not cookiecutter:
        exit_msg('cookiecutter must be installed')
    check_git_diff(ctx, direct_abort=True)
    cc_context = cookiecutter_context()
    sync_metadata = sync_meta()
    pinned_version = sync_metadata['sync'].get('pinned_version')

    os.chdir(root_path())

    print('#' * 80)
    version = get_sync_version(version=version, pinned_version=pinned_version)

    # TODO: as further improvement we could read "last_sync" date
    # and if the date was too far away in the past
    # we can show a more prominent warning
    if os.getenv('PROJECT_SYNC_FORCE'):
        # this feature should not land into task params
        # to dis-encourage its usage.
        # It's here only for huge maintenance tasks
        # whereas we might want to run several sync sessions on many projs.
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('PROJECT_SYNC_FORCE mode on: skipping confirmation')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    else:
        ask_or_abort(
            "Selected version: {}. Are you sure it's correct?".format(version)
        )
    update_sync_meta({'pinned_version': version, 'last_sync': now()})
    print('Pinned version updated.')
    print('#' * 80)

    git_repo = TEMPLATE_GIT
    if fork:
        # use different remote
        git_repo = TEMPLATE_GIT_REPO_URL.format(fork)
    elif fork_url:
        git_repo = fork_url
    if fork or fork_url:
        print('Using fork:', git_repo)

    _do_sync(ctx, cc_context, version, git_repo, sync_metadata, commit=commit)


def _do_sync(ctx, cc_context, version, git_repo, sync_metadata, commit=True):
    with tempdir() as tmp:
        cookiecutter(
            git_repo,
            checkout=version,
            no_input=True,
            extra_context=cc_context,
            output_dir=tmp,
            overwrite_if_exists=True,
        )
        template = os.path.join(tmp, cc_context['repo_name'])
        selected_files = set()
        with cd(template):
            include = sync_metadata['sync'].get('include', [])
            exclude = sync_metadata['sync'].get('exclude', []) + GIT_IGNORES
            comment = sync_metadata['sync'].get('comment', '')
            for root, dirs, files in os.walk('.', topdown=True):
                if exclude:
                    dirs[:] = _exclude_fnmatch(root, dirs, exclude)
                    files[:] = _exclude_fnmatch(root, files, exclude)
                syncfiles = [os.path.join(root, f) for f in files]
                for incl in include:
                    selected_files.update(fnmatch.filter(syncfiles, incl))

            print('Syncing files:')
            for s in sorted(selected_files):
                print('* {}'.format(s))

        for relpath in selected_files:
            source = os.path.join(template, relpath)
            target_dir = os.path.dirname(relpath)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            shutil.copy(source, relpath)
            if os.path.isfile(relpath):
                add_comment(relpath, comment)

        # update metadata too
        selected_files.add('.sync.yml')
        ctx.run('git add {}'.format(' '.join(selected_files)))
        if commit:
            msg = 'Update project from odoo-template ver: {}'.format(version)
            ctx.run('git commit -m "{}" -e -vv'.format(msg), pty=True)
