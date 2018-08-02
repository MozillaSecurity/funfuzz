# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions here interact with Amazon EC2 using boto.
"""

from __future__ import absolute_import, division, print_function, unicode_literals  # isort:skip

from builtins import object
import logging
import os
import platform
import shutil
import sys

import boto.exception
from boto.s3.connection import Key
from boto.s3.connection import S3Connection
import boto.utils

if sys.version_info.major == 2:
    import logging_tz  # pylint: disable=import-error

FUNFUZZ_LOG = logging.getLogger("funfuzz")
FUNFUZZ_LOG.setLevel(logging.INFO)
LOG_HANDLER = logging.StreamHandler()
if sys.version_info.major == 2:
    LOG_FORMATTER = logging_tz.LocalFormatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                              fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
else:
    LOG_FORMATTER = logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S%z]",
                                      fmt="%(asctime)s %(name)s %(levelname)-8s %(message)s")
LOG_HANDLER.setFormatter(LOG_FORMATTER)
FUNFUZZ_LOG.addHandler(LOG_HANDLER)


def isEC2VM():  # pylint: disable=invalid-name,missing-return-doc,missing-return-type-doc
    """Test to see if the specified S3 cache is available, but only on non-WSL Linux systems."""
    if not (platform.system() == "Linux" and "Microsoft" not in platform.release()):
        return False

    try:
        return bool(boto.utils.get_instance_metadata(num_retries=1, timeout=1)["instance-id"])
    except KeyError:
        return False


class S3Cache(object):  # pylint: disable=missing-docstring
    def __init__(self, bucket_name):
        self.bucket = None
        self.bucket_name = bucket_name

    def connect(self):  # pylint: disable=missing-return-doc,missing-return-type-doc
        """Connect to the S3 bucket, but only on non-WSL Linux systems."""
        if not (platform.system() == "Linux" and "Microsoft" not in platform.release()):
            return False

        EC2_PROFILE = None if isEC2VM() else "laniakea"  # pylint: disable=invalid-name
        try:
            conn = S3Connection(profile_name=EC2_PROFILE)
            self.bucket = conn.get_bucket(self.bucket_name)
            return True
        except boto.provider.ProfileNotFoundError:
            FUNFUZZ_LOG.warning('Unable to connect via boto using profile name "%s" in ~/.boto', EC2_PROFILE)
            return False
        except boto.exception.S3ResponseError:
            FUNFUZZ_LOG.warning('Unable to connect to the following bucket "%s", please check your credentials.',
                                self.bucket_name)
            return False

    def downloadFile(self, origin, dest):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
        # pylint: disable=missing-return-type-doc,missing-type-doc
        """Download files from S3."""
        key = self.bucket.get_key(origin)
        if key is not None:
            key.get_contents_to_filename(dest)
            FUNFUZZ_LOG.info("Finished downloading.")
            return True
        return False

    def compressAndUploadDirTarball(self, directory, tarball_path):  # pylint: disable=invalid-name,missing-param-doc
        # pylint: disable=missing-type-doc
        """Compress a directory into a bz2 tarball and upload it to S3."""
        FUNFUZZ_LOG.info("Creating archive...")
        shutil.make_archive(directory, "bztar", directory)
        self.uploadFileToS3(tarball_path)

    def uploadFileToS3(self, filename):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
        """Upload file to S3."""
        # Root folder of the S3 bucket
        destDir = ""  # pylint: disable=invalid-name
        destpath = os.path.join(destDir, os.path.basename(filename))
        FUNFUZZ_LOG.info("Uploading %s to Amazon S3 bucket %s", filename, self.bucket_name)

        k = Key(self.bucket)
        k.key = destpath
        k.set_contents_from_filename(filename, reduced_redundancy=True)

    def uploadStrToS3(self, destDir, filename, contents):  # pylint: disable=invalid-name,missing-param-doc
        # pylint: disable=missing-type-doc
        """Upload a string to an S3 file."""
        FUNFUZZ_LOG.info("Uploading %s to Amazon S3 bucket %s", filename, self.bucket_name)

        k2 = Key(self.bucket)  # pylint: disable=invalid-name
        k2.key = os.path.join(destDir, filename)
        k2.set_contents_from_string(contents, reduced_redundancy=True)
        FUNFUZZ_LOG.info("")  # This newline is needed to get the path of the compiled binary, output on a newline.
