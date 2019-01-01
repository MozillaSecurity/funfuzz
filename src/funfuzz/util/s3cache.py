# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Functions here interact with Amazon EC2 using boto.
"""

import os
import platform
import shutil

import boto.exception
from boto.s3.connection import Key
from boto.s3.connection import S3Connection
import boto.utils


def isEC2VM():  # pylint: disable=invalid-name,missing-return-doc,missing-return-type-doc
    """Test to see if the specified S3 cache is available, but only on non-WSL Linux systems."""
    if not (platform.system() == "Linux" and "Microsoft" not in platform.release()):
        return False

    try:
        return bool(boto.utils.get_instance_metadata(num_retries=1, timeout=1)["instance-id"])
    except KeyError:
        return False


class S3Cache:  # pylint: disable=missing-docstring
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
            print(f'Unable to connect via boto using profile name "{EC2_PROFILE}" in ~/.boto')
            return False
        except boto.exception.S3ResponseError:
            print(f'Unable to connect to the following bucket "{self.bucket_name}", please check your credentials.')
            return False

    def downloadFile(self, origin, dest):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
        # pylint: disable=missing-return-type-doc,missing-type-doc
        """Download files from S3."""
        key = self.bucket.get_key(origin)
        if key is not None:
            key.get_contents_to_filename(dest)
            print("Finished downloading.")
            return True
        return False

    def compressAndUploadDirTarball(self, directory, tarball_path):  # pylint: disable=invalid-name,missing-param-doc
        # pylint: disable=missing-type-doc
        """Compress a directory into a bz2 tarball and upload it to S3."""
        print("Creating archive...")
        shutil.make_archive(directory, "bztar", directory)
        self.uploadFileToS3(tarball_path)

    def uploadFileToS3(self, filename):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
        """Upload file to S3."""
        # Root folder of the S3 bucket
        destDir = ""  # pylint: disable=invalid-name
        destpath = os.path.join(destDir, os.path.basename(filename))
        print(f"Uploading {filename} to Amazon S3 bucket {self.bucket_name}")

        k = Key(self.bucket)
        k.key = destpath
        k.set_contents_from_filename(filename, reduced_redundancy=True)

    def uploadStrToS3(self, destDir, filename, contents):  # pylint: disable=invalid-name,missing-param-doc
        # pylint: disable=missing-type-doc
        """Upload a string to an S3 file."""
        print(f"Uploading {filename} to Amazon S3 bucket {self.bucket_name}")

        k2 = Key(self.bucket)  # pylint: disable=invalid-name
        k2.key = os.path.join(destDir, filename)
        k2.set_contents_from_string(contents, reduced_redundancy=True)
        print()  # This newline is needed to get the path of the compiled binary printed on a newline.
