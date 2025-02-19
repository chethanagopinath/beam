# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Module implements CI/CD steps for Beam Playground examples
"""
import argparse
import asyncio
import logging
import os
from typing import List

from models import SdkEnum, Example, StringToSdkEnum
from config import Config, Origin
from datastore_client import DatastoreClient
from api.v1 import api_pb2
from verify import Verifier
from helper import (
    find_examples,
    load_supported_categories,
    validate_examples_for_duplicates_by_name,
)
from logger import setup_logger

parser = argparse.ArgumentParser(description="CI/CD Steps for Playground objects")
parser.add_argument(
    "--step",
    dest="step",
    required=True,
    help="CI step to verify all beam examples/tests/katas. CD step to save all "
    "beam examples/tests/katas and their outputs on the GCD",
    choices=[Config.CI_STEP_NAME, Config.CD_STEP_NAME],
)
parser.add_argument(
    "--sdk",
    dest="sdk",
    required=True,
    help="Supported SDKs",
    choices=Config.SUPPORTED_SDK,
)
parser.add_argument(
    "--origin",
    type=Origin,
    required=True,
    help="ORIGIN field of pg_examples/pg_snippets",
    choices=[o.value for o in [Origin.PG_EXAMPLES, Origin.TB_EXAMPLES]],
)
parser.add_argument(
    "--subdirs",
    default=[],
    nargs="+",
    required=True,
    help="limit sub directories to walk through, relative to BEAM_ROOT_DIR",
)

root_dir = os.getenv("BEAM_ROOT_DIR")
categories_file = os.getenv("BEAM_EXAMPLE_CATEGORIES")


def _check_envs():
    if root_dir is None:
        raise KeyError("BEAM_ROOT_DIR environment variable should be specified in os")
    if categories_file is None:
        raise KeyError(
            "BEAM_EXAMPLE_CATEGORIES environment variable should be specified in os"
        )


def _run_ci_cd(step: str, raw_sdk: str, origin: Origin, subdirs: List[str]):
    sdk: SdkEnum = StringToSdkEnum(raw_sdk)

    load_supported_categories(categories_file)
    logging.info("Start of searching Playground examples ...")
    examples = find_examples(root_dir, subdirs, sdk)
    validate_examples_for_duplicates_by_name(examples)
    logging.info("Finish of searching Playground examples")
    logging.info("Number of found Playground examples: %s", len(examples))

    examples = list(filter(lambda example: example.tag.multifile is False, examples))
    logging.info("Number of sinlge-file Playground examples: %s", len(examples))

    logging.info("Execute Playground examples ...")
    runner = Verifier(sdk, origin)
    runner.run_verify(examples)

    if step == Config.CD_STEP_NAME:
        logging.info("Start of sending Playground examples to the Cloud Datastore ...")
        datastore_client = DatastoreClient()
        datastore_client.save_catalogs()
        datastore_client.save_to_cloud_datastore(examples, sdk, origin)
        logging.info("Finish of sending Playground examples to the Cloud Datastore")


if __name__ == "__main__":
    parser = parser.parse_args()
    _check_envs()
    setup_logger()
    _run_ci_cd(parser.step, parser.sdk, parser.origin, parser.subdirs)
