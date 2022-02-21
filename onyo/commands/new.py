#!/usr/bin/env python3

import subprocess
import logging
import os
import sys
import argparse

logging.basicConfig()
logger = logging.getLogger('onyo')


def run_cmd(cmd, comment=""):
    if comment != "":
        run_process = subprocess.Popen(cmd.split() + [comment],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
    else:
        run_process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, universal_newlines=True)
    run_output, run_error = run_process.communicate()
    if (run_error != ""):
        logger.error(run_error)
        sys.exit(0)
    else:
        logger.info(cmd + " " + comment)


def build_commit_cmd(file):
    return ["git commit -m", "\'add " + file + " to onyo\'"]


def run_onyo_new(location):
    if not os.path.isdir(location):
        logger.error(location + " does not exist.")
        sys.exit(0)

    type_str = str(input('<type>*:'))
    make_str = str(input('<make>*:'))
    model_str = str(input('<model*>:'))
    serial_str = str(input('<serial*>:'))
    filename = create_filename(type_str, make_str, model_str, serial_str)
    run_cmd(create_asset_file_cmd(location, filename))
    git_add_cmd = build_git_add_cmd(location + "/" + filename)
    run_cmd(git_add_cmd)
    return location + "/" + filename


def create_filename(type_str, make_str, model_str, serial_str):
    filename = type_str + "_" + make_str + "_" + model_str + "." + serial_str
    return filename


def build_git_add_cmd(file):
    return "git add " + file


def create_asset_file_cmd(location, filename):
    return "touch " + location + "/" + filename


def new(args):
    # create file for asset, fill in fields
    created_file = run_onyo_new(args.location)

    # build commit command
    [commit_cmd, commit_msg] = build_commit_cmd(created_file)

    # run commands
    run_cmd(commit_cmd, commit_msg)
