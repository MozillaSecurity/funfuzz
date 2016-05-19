#!/usr/bin/env python
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import shutil
import sys

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, os.pardir, 'util'))
sys.path.append(path1)
import subprocesses as sps

isBoto = False
# We need to first install boto into MozillaBuild via psbootstrap on Windows
if not (sps.isMac or sps.isWin):
    try:
        from boto.s3.connection import S3Connection, Key
        import boto.exception
        import boto.utils  # Cannot find this if only boto is imported
        isBoto = True
    except ImportError:
        isBoto = False


def isEC2VM():
    """Test to see if the specified S3 cache is available."""
    if sps.isMac or not isBoto:
        return False

    if not sps.isWin:  # We need to first install boto into MozillaBuild via psbootstrap on Windows
        try:
            return bool(boto.utils.get_instance_metadata(num_retries=1, timeout=1)['instance-id'])
        except KeyError:
            return False


class S3Cache(object):
    def __init__(self, bucket_name):
        self.bucket = None
        self.bucket_name = bucket_name

    def connect(self):
        """Connect to the S3 bucket."""
        if not isBoto:
            return False

        EC2_PROFILE = None if isEC2VM() else 'laniakea'
        try:
            conn = S3Connection(profile_name=EC2_PROFILE)
            self.bucket = conn.get_bucket(self.bucket_name)
            return True
        except boto.provider.ProfileNotFoundError:
            print 'Unable to connect via boto using profile name "%s" in ~/.boto' % EC2_PROFILE
            return False
        except boto.exception.S3ResponseError:
            print 'Unable to connect to the following bucket "%s", please check your credentials.' % self.bucket_name
            return False

    def downloadFile(self, origin, dest):
        """Download files from S3."""
        key = self.bucket.get_key(origin)
        if key is not None:
            key.get_contents_to_filename(dest)
            print 'Finished downloading.'
            return True
        else:
            return False

    def compressAndUploadDirTarball(self, directory, tarball_path):
        """Compress a directory into a bz2 tarball and upload it to S3."""
        print 'Creating archive...'
        shutil.make_archive(directory, 'bztar', directory)
        self.uploadFileToS3(tarball_path)

    def uploadFileToS3(self, filename):
        """Upload file to S3."""
        destDir = ''  # Root folder of the S3 bucket
        destpath = os.path.join(destDir, os.path.basename(filename))
        print 'Uploading %s to Amazon S3 bucket %s' % (filename, self.bucket_name)

        k = Key(self.bucket)
        k.key = destpath
        k.set_contents_from_filename(filename, reduced_redundancy=True)

    def uploadStrToS3(self, destDir, filename, contents):
        """Upload a string to an S3 file."""
        print 'Uploading %s to Amazon S3 bucket %s' % (filename, self.bucket_name)

        k2 = Key(self.bucket)
        k2.key = os.path.join(destDir, filename)
        k2.set_contents_from_string(contents, reduced_redundancy=True)
        print  # This newline is needed to get the path of the compiled binary printed on a newline.
