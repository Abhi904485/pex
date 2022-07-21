import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from functools import wraps
from tenacity import retry, RetryError, stop_after_attempt, retry_if_exception_type, wait_random_exponential

import boto3
from botocore.exceptions import ClientError
from ec2_metadata import ec2_metadata
from agentless.logger import create_logger
from agentless.utility import Utility
import logging.config

# Removed unnecessary logging from boto3, requests, botocore, ec2_metadata, retrying etc
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
})


def retry_if_exception(error):
    return isinstance(error, RetryError)


def method_start_end(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        log.debug("{} +++".format(func.__name__), extra={'scanId': None, 'tenantId': None})
        res = func(*args, **kwargs)
        log.debug("{} ---".format(func.__name__), extra={'scanId': None, 'tenantId': None})
        return res

    return func_wrapper


class AgentLess:

    def __init__(self, logger, utility):
        self.ec2_instance_id = ec2_metadata.instance_id
        self.ec2_client = None
        self.s3_client = None
        self.extra = {'scanId': None, 'tenantId': None}
        self.device = None
        self.device_m = None
        self.cache = {}
        self.logger = logger
        self.tenant_id = None
        self.scan_id = None
        self.snapshot_data = None
        self.bucket_name = None
        self.instance_role = None
        self.utility = utility

    @method_start_end
    def get_session(self):
        """
        Getting AWS Session
        :return: obj
        """
        if 'session' not in self.cache:
            boto3.setup_default_session(region_name=ec2_metadata.region)
            self.cache['session'] = boto3.DEFAULT_SESSION
            self.logger.info("Creation Session..", extra=self.extra)
        return self.cache['session']

    @method_start_end
    @retry(stop=stop_after_attempt(10), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def get_ec2_client(self):
        """
        Getting Ec2 Client
        :return: obj
        """
        try:
            return self.get_session().client("ec2")
        except Exception as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            raise RetryError("Retrying Again")

    @method_start_end
    @retry(stop=stop_after_attempt(10), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def get_s3_client(self, ):
        """
        Get S3 Client
        :return: obj
        """
        try:
            return self.get_session().client("s3")
        except Exception as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            raise RetryError("Retrying Again")

    @method_start_end
    @retry(stop=stop_after_attempt(10), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def upload_to_s3(self, file_path, bucket_name, object_name):
        """
        Upload to S3
        :param file_path: str
        :param bucket_name: str
        :param object_name: str
        :return: bool
        """
        self.logger.info("Uploading started: to S3 at location: {} bucket name: {} file_path: {}".format(object_name, bucket_name, file_path), extra=self.extra)
        try:
            self.get_s3_client().upload_file(file_path, bucket_name, object_name)
            self.logger.info("Uploading Completed: to S3 at location: {} bucket name: {} file_path: {}".format(object_name, bucket_name, file_path), extra=self.extra)
            return True
        except ClientError as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            raise RetryError("Retrying Again")

    @method_start_end
    def create_path_with_parent_directory_if_not_exists(self, path):
        """
        Create path with leaves if path does not exist
        :param path: str
        :return: bool
        """
        if os.path.exists(path):
            self.logger.warning("{} already exists".format(path), extra=self.extra)
            return True
        else:
            self.logger.debug("Creating path {}".format(path), extra=self.extra)
            try:
                os.makedirs(path)
                self.logger.debug("Created path {}".format(path), extra=self.extra)
                return True
            except Exception as e:
                self.logger.exception("Unable to create path {} with leaves {}".format(path, e), extra=self.extra)
                return False

    @method_start_end
    def collect_va_files(self, mounted_path, folder_name):
        """
        Gathering Required Files according to mentioned path list from Current OS and copying contents of existing directories under layerfiles location
        :param mounted_path: str
        :param folder_name: str
        :return: bool
        """
        # Path till layerfiles /mnt/tenant_id/scan_id/instance_id/snapshot_id/layerfiles
        layerfiles_path = os.path.join(mounted_path, folder_name)
        if not self.create_path_with_parent_directory_if_not_exists(path=layerfiles_path):
            self.logger.error("layerfiles_path {} creation Failed".format(layerfiles_path), extra=self.extra)
            return False
        to_hash = ""
        self.logger.info("Gathering required files for VM\n", extra=self.extra)
        path_list = ["/lib/apk/db/installed",
                     "/var/lib/dpkg/status",
                     "/var/lib/rpm/Packages",
                     "/etc/alpine-release",
                     "/etc/apt/sources.list",
                     "/etc/lsb-release",
                     "/etc/os-release",
                     "/usr/lib/os-release",
                     "/etc/oracle-release",
                     "/etc/centos-release",
                     "/etc/redhat-release",
                     "/etc/system-release",
                     "/var/lib/dpkg/status-old",
                     "/etc/apt/sources.list.d/pgdg.list"]
        # command = "mount - o nouuid ${} /mnt/{}/{}/{}/{}".format(tenant_id, scan_id, device_, instance_id_, snapshot_id_)
        for _path in path_list:
            # source_path = /mnt/tenant_id/scan_id/instance_id/snapshot_id/lib/apk/db/installed
            # mounted_path = /mnt/tenant_id/scan_id/instance_id/snapshot_id
            source_path = os.path.join(mounted_path, _path.lstrip("/").strip())
            if not os.path.exists(source_path):
                continue
            # intermediate_path =lib/apk/db
            intermediate_path = _path.rsplit("/", 1)[0].lstrip("/").strip()
            # destination_path = /mnt/tenant_id/scan_id/instance_id/snapshot_id/layerfiles/lib/apk/db
            destination_path = os.path.join(layerfiles_path, intermediate_path)
            if not self.create_path_with_parent_directory_if_not_exists(destination_path):
                self.logger.error("destination_path {} creation Failed".format(destination_path), extra=self.extra)
                return False
            # source_path = /mnt/tenant_id/scan_id/instance_id/snapshot_id/lib/apk/db/installed   destination_path = /mnt/tenant_id/scan_id/instance_id/snapshot_id/layerfiles/lib/apk/db
            self.logger.info("Copying files from source_path {} to destination_path {}".format(source_path, destination_path), extra=self.extra)
            shutil.copy(source_path, destination_path)
            to_hash += os.path.join(" ", folder_name, _path.lstrip("/").strip())
        return to_hash

    @method_start_end
    def create_checksum(self, hashable_string):
        """
        Creating sha256 hash
        :param hashable_string: str
        :return: string
        """
        checksum = hashlib.sha256(hashable_string.encode('utf-8')).hexdigest()
        self.logger.info("Created checksum {}".format(checksum), extra=self.extra)
        return checksum

    @method_start_end
    def create_tar_file(self, file_path, source_dir):
        """
        Creating Tar file using python tar module
        :param file_path: str
        :param source_dir: str
        :return:
        """
        try:
            with tarfile.open(file_path, "w:gz") as tar:
                tar.add(source_dir, arcname=os.path.basename(source_dir))
            self.logger.debug("Tar {} Created".format(file_path), extra=self.extra)
            return bool(os.path.join(source_dir, file_path))
        except Exception as e:
            self.logger.exception("Tar Creation failed {}".format(e), extra=self.extra)
            return False

    @method_start_end
    def move_tar_into_checksum_location(self, src, dest):
        """
        Move Tar file under tosend/checksum location
        :param src: str
        :param dest: str
        :return: bool
        """
        try:
            shutil.move(src, dest)
            self.logger.debug("layer.tar moved from {} {}".format(src, dest), extra=self.extra)
            return True
        except Exception as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            return False

    @method_start_end
    def create_manifest(self, path, layer_hash):
        """
        Creating manifest file under tosend location
        :param path: str
        :param layer_hash: str
        :return: bool
        """
        try:
            manifest_dict = [
                {
                    "RepoTags": [
                        "vm"
                    ],
                    "Layers": [
                        "{}/layer.tar".format(layer_hash)
                    ]
                }
            ]
            out_file = open(os.path.join(path, 'manifest.json'), 'w')
            json.dump(manifest_dict, out_file, indent=3)
            self.logger.debug("manifest.json created", extra=self.extra)
            return True
        except Exception as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            return False

    @method_start_end
    def create_volume(self, snapshot_id, count=0):
        """
        Create Volume
        :param count: int
        :param snapshot_id: str
        :return: str or None
        """

        client = self.get_ec2_client()
        response = self._create_volume(client, snapshot_id)
        volume_id = response["VolumeId"]
        return self.is_volume_ready(count, volume_id)

    @method_start_end
    def is_volume_ready(self, count, volume_id):
        """
        Check volume is up or not for attach
        :param count: int
        :param volume_id: str
        :return: str/bool
        """
        state = self.describe_volume(volume_id=volume_id)
        while state != "available":
            time.sleep(5)
            state = self.describe_volume(volume_id=volume_id)
            if count == 10:
                self.logger.error("Volume creation timed out!".format(volume_id), extra=self.extra)
                return False
            count += 1
        else:
            self.logger.debug("State is {} for Volume id {}".format(state, volume_id), extra=self.extra)
            return volume_id

    @method_start_end
    @retry(stop=stop_after_attempt(15), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def _create_volume(self, client, snapshot_id):
        """
        Private Create Volume
        :param client: obj
        :param snapshot_id: str
        :return:
        """
        try:
            response = client.create_volume(
                AvailabilityZone=ec2_metadata.availability_zone,
                Iops=100,
                SnapshotId=snapshot_id,
                VolumeType='io1',
                MultiAttachEnabled=True,
            )
            return response
        except Exception as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            raise RetryError("Retrying Again Private Create volume")

    @method_start_end
    def attach_volume(self, instance_id, volume_id, count=0):
        """
        Attach Volume
        :param count: int
        :param instance_id: str
        :param volume_id: str
        :return: bool
        """
        client = self.get_ec2_client()
        self._attach_volume(client, instance_id, volume_id)
        return self.is_volume_attached(count, instance_id, volume_id)

    @method_start_end
    def is_volume_attached(self, count, instance_id, volume_id):
        """
        Check if volume Attached or not
        :param count: int
        :param instance_id: str
        :param volume_id: str
        :return: bool
        """
        state = self.describe_volume(volume_id=volume_id)
        while state != 'in-use':
            time.sleep(5)
            state = self.describe_volume(volume_id=volume_id)
            if count == 10:
                self.logger.error("Attaching Volume timeout", extra=self.extra)
                return False
            count += 1
        else:
            self.logger.debug("State is {} for volume {} and instance {}".format(state, volume_id, instance_id), extra=self.extra)
            return True

    @method_start_end
    @retry(stop=stop_after_attempt(15), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def _attach_volume(self, client, instance_id, volume_id):
        """
        Private Attach Volume
        :param client: obj
        :param instance_id: str
        :param volume_id: str
        :return:
        """
        try:
            client.attach_volume(
                Device=self.device,
                InstanceId=instance_id,
                VolumeId=volume_id,
            )
        except Exception as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            self.device = self.get_device()
            raise RetryError("Retrying Again Private Attach volume")

    @method_start_end
    @retry(stop=stop_after_attempt(15), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def describe_volume(self, volume_id):
        """
        Describe Volume
        :param volume_id: str
        :return: str
        """
        client = self.get_ec2_client()
        try:
            response = client.describe_volumes(
                VolumeIds=[
                    volume_id
                ]
            )
            return response["Volumes"][0]["State"]
        except Exception as e:
            self.logger.exception(str(e.args[0]), extra=self.extra)
            raise RetryError("Retrying Again Describe volume..")

    @method_start_end
    def detach_volume(self, instance_id, volume_id, count=0):
        """
        Detach Volume
        :param count: int
        :param instance_id: str
        :param volume_id: str
        :return: bool
        """
        client = self.get_ec2_client()
        self._detach_volume(client, instance_id, volume_id)
        return self.is_volume_detached(count, instance_id, volume_id)

    @method_start_end
    def is_volume_detached(self, count, instance_id, volume_id):
        """
        Is Volume Detached
        :param count: int
        :param instance_id: str
        :param volume_id: str
        :return: bool
        """
        state = self.describe_volume(volume_id=volume_id)
        while state != 'available':
            time.sleep(5)
            state = self.describe_volume(volume_id=volume_id)
            if count == 10:
                self.logger.error("DeAttaching Volume timeout!", extra=self.extra)
                return False
            count += 1
        else:
            self.logger.debug("State is {} for volume {} and instance {}".format(state, volume_id, instance_id), extra=self.extra)
            return True

    @method_start_end
    @retry(stop=stop_after_attempt(15), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def _detach_volume(self, client, instance_id, volume_id):
        """
        Private Detach Volume
        :param client: obj
        :param instance_id: str
        :param volume_id: str
        :return:
        """
        try:
            client.detach_volume(
                Device=self.device,
                Force=True,
                InstanceId=instance_id,
                VolumeId=volume_id
            )
        except Exception as e:
            self.logger.exception(str(e.args[0]) + "retrying Private Detach Volume", extra=self.extra)
            raise RetryError("Retrying Again")

    @method_start_end
    @retry(stop=stop_after_attempt(15), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def mount_volume(self, path, tenant_id, scan_id, instance_id, snapshot_id):
        """
        Mount Volume
        :param path: str
        :param scan_id: str
        :param tenant_id: str
        :param instance_id: str
        :param snapshot_id: str
        :return: bool
        """
        self.device_m = self.get_device_mount()
        try:
            format_dict = {
                "path": path,
                "device": self.device_m,
                "instance_id": instance_id,
                "snapshot_id": snapshot_id,
                "tenant_id": tenant_id,
                "scan_id": scan_id
            }
            command = "mount -o nouuid {device} {path}/{tenant_id}/{scan_id}/{instance_id}/{snapshot_id}".format(**format_dict)
            return_code = subprocess.call([command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            return not bool(return_code)
        except Exception as e:
            self.logger.exception(str(e.args[0]) + "retrying Mount Volume", extra=self.extra)
            raise RetryError("Retrying Again")

    @method_start_end
    @retry(stop=stop_after_attempt(15), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def unmount_volume(self):
        """
        Unmount volume
        :return: bool
        """
        try:
            command = "umount --force {}".format(self.device_m)
            return_code = subprocess.call([command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            return not bool(return_code)
        except Exception as e:
            self.logger.exception(str(e.args[0]) + "retrying Unmount Volume", extra=self.extra)
            raise RetryError("Retrying Again")

    @method_start_end
    def parse_args(self, param_string):
        json_data = json.loads(param_string)
        tenant_id = json_data["tenantId"]
        scan_id = json_data["scanId"]
        snapshot_data_ = json_data["snapshotData"]
        bucket_name = json_data["bucketName"]
        instance_role = json_data["roleName"]
        self.logger.info("tenantId = {tenantId} scanId={scanId} bucketName={bucketName} instanceRole={roleName}".format(**json_data), extra=self.extra)
        return tenant_id, scan_id, snapshot_data_, bucket_name, instance_role

    @method_start_end
    def get_device(self, count=0):
        """
        Get Available Device for attaching
        :param count: int
        :return: bool
        """
        self.device = self.utility.get_device(logger=self.logger, extra=self.extra)['device']
        while not self.device:
            self.logger.info("No devices are free retrying again", extra=self.extra)
            time.sleep(5)
            self.device = self.utility.get_device(logger=self.logger, extra=self.extra)['device']
            if count == 20:
                self.logger.error("Devices timeout!", extra=self.extra)
                return False
            count += 1
        else:
            return self.device

    @method_start_end
    def get_device_mount(self, count=0):
        """
        Get Available Device for mounting
        :param count: int
        :return: bool
        """
        self.device_m = self.utility.get_device_mount(logger=self.logger, extra=self.extra)['device']
        while not self.device_m:
            self.logger.info("No new mounted device found retrying again", extra=self.extra)
            time.sleep(5)
            self.device_m = self.utility.get_device_mount(logger=self.logger, extra=self.extra)['device']
            if count == 20:
                self.logger.error("Devices timeout!", extra=self.extra)
                return False
            count += 1
        else:
            return self.device_m

    @method_start_end
    def delete_volume(self, volume_id):
        """
        Delete Volume
        :param volume_id: str
        :return: bool
        """
        client = self.get_ec2_client()
        response = self._delete_volume(client, volume_id)
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            self.logger.debug("Volume {} deleted ".format(volume_id), extra=self.extra)
            return True
        else:
            self.logger.error("Volume {} deletion timeout ".format(volume_id), extra=self.extra)
            return False

    @method_start_end
    @retry(stop=stop_after_attempt(15), wait=wait_random_exponential(multiplier=0.5, max=45), retry=retry_if_exception_type(RetryError))
    def _delete_volume(self, client, volume_id):
        """
        Private Delete Volume
        :param client: obj
        :param volume_id: str
        :return: dict
        """
        try:
            response = client.delete_volume(
                VolumeId=volume_id,
            )
            return response
        except Exception as e:
            self.logger.exception(str(e.args[0]) + "retrying Private Delete Volume", extra=self.extra)
            raise RetryError("Retrying Again Private Delete Volume")

    def main(self, instance_id, snapshot_id):
        folder = "layerfiles"
        tar_file_name = "layer.tar"
        tosend = 'tosend'
        # todo path need to decide
        path = r"/mnt"
        tosend_tar_gz = "tosend.tar.gz"
        volume_id = self.create_volume(snapshot_id=snapshot_id)
        self.device = self.get_device()
        if not volume_id:
            self.logger.error("There is some problem in creating volume", extra=self.extra)
            raise Exception("There is some problem in creating volume")
        if not self.device:
            self.logger.error("There is some problem in getting device", extra=self.extra)
            raise Exception("There is some problem in getting device")
        self.logger.info("Volume_id ={} device= {}".format(volume_id, self.device), extra=self.extra)
        if not self.attach_volume(instance_id=self.ec2_instance_id, volume_id=volume_id):
            self.logger.error("There is some problem in attaching Volume {} on instance_id {}".format(volume_id, self.ec2_instance_id), extra=self.extra)
            raise Exception("There is some problem in attaching Volume {} on instance_id {}".format(volume_id, self.ec2_instance_id))
        # mounted_path = /mnt/tenant_id/scan_id/instance_id/snapshot_id
        mounted_path = "{}/{}/{}/{}/{}".format(path, self.tenant_id, self.scan_id, instance_id, snapshot_id)
        if not self.create_path_with_parent_directory_if_not_exists(path=mounted_path):
            self.logger.error("mounted_path {} creation failed".format(mounted_path), extra=self.extra)
            raise Exception("mounted_path {} creation failed".format(mounted_path))

        if not self.mount_volume(path=path, tenant_id=self.tenant_id, scan_id=self.scan_id, instance_id=self.ec2_instance_id, snapshot_id=snapshot_id):
            self.detach_volume(instance_id=self.ec2_instance_id, volume_id=volume_id)
            self.utility.release_device(device=self.device, logger=self.logger, extra=self.extra)
            self.delete_volume(volume_id=volume_id)
            self.cleanup_directories(path=path)
            self.logger.error("There is some problem in mounting volume", extra=self.extra)
            raise Exception("There is some problem in mounting volume")

        file_hash = self.collect_va_files(mounted_path=mounted_path, folder_name=folder)
        if not file_hash:
            self.cleanup(self.ec2_instance_id, path, volume_id)
            self.logger.error("file_hash = {} ".format(file_hash), extra=self.extra)
            raise Exception("file_hash = {}".format(file_hash))
        # creating tar of layerfiles dir for ex: /mnt/tenant_id/scan_id/instance_id/snapshot_id/layerfiles
        if not self.create_tar_file(file_path=os.path.join(os.path.dirname(os.path.join(mounted_path, folder)), tar_file_name), source_dir=os.path.join(mounted_path, folder)):
            self.cleanup(self.ec2_instance_id, path, volume_id)
            self.logger.error("Tar file {} creation with path {} failed !".format(tar_file_name, os.path.join(os.path.dirname(os.path.join(mounted_path, folder)), tar_file_name)), extra=self.extra)
            raise Exception("Tar file {} creation with path {} failed !".format(tar_file_name, os.path.join(os.path.dirname(os.path.join(mounted_path, folder)), tar_file_name)))
        checksum, checksum_location = self.create_checksum_and_location(file_hash, mounted_path)
        if not checksum or not checksum_location:
            self.cleanup(self.ec2_instance_id, path, volume_id)
            self.logger.error("Checksum and Checksum location creation failed", extra=self.extra)
            raise Exception("Checksum and Checksum location creation failed")
        if not self.create_manifest(path=os.path.join(mounted_path, tosend), layer_hash=checksum):
            self.cleanup(self.ec2_instance_id, path, volume_id)
            self.logger.error("Unable To Create Manifest in path {} ".format(os.path.join(mounted_path, tosend)), extra=self.extra)
            raise Exception("Unable To Create Manifest in path {} ".format(os.path.join(mounted_path, tosend)))
        tar_file_location = os.path.join(mounted_path, tar_file_name)
        if not self.move_tar_into_checksum_location(tar_file_location, checksum_location):
            self.cleanup(self.ec2_instance_id, path, volume_id)
            self.logger.error("Tar file move from src {} to dest {} failed !".format(tar_file_location, checksum_location), extra=self.extra)
            raise Exception("Tar file move from src {} to dest {} failed !".format(tar_file_location, checksum_location))
        # creating tar of tosend dir for ex: /mnt/tenant_id/scan_id/instance_id/snapshot_id/tosend
        if not self.create_tar_file(file_path=os.path.join(os.path.dirname(os.path.join(mounted_path, tosend)), tosend_tar_gz), source_dir=os.path.join(mounted_path, tosend)):
            self.cleanup(self.ec2_instance_id, path, volume_id)
            self.logger.error("Tar file {} creation with path {} failed !".format(tosend_tar_gz, os.path.join(os.path.dirname(os.path.join(mounted_path, tosend)), tosend_tar_gz)), extra=self.extra)
            raise Exception("Tar file {} creation with path {} failed !".format(tosend_tar_gz, os.path.join(os.path.dirname(os.path.join(mounted_path, tosend)), tosend_tar_gz)))
        # uploading tosend_tar_gz into s3
        if not self.upload_to_s3(file_path=os.path.join(mounted_path, tosend_tar_gz), bucket_name=self.bucket_name, object_name=os.path.join('agentless-va', str(self.tenant_id), str(self.scan_id), str(instance_id), str(snapshot_id), tosend_tar_gz)):
            self.cleanup(self.ec2_instance_id, path, volume_id)
            self.logger.error("Upload To S3 Failed", extra=self.extra)
            raise Exception("Upload To S3 Failed")
        # Unmount Volume
        if not self.unmount_volume():
            self.utility.release_device_mount(device=self.device_m, logger=self.logger, extra=self.extra)
            self.detach_volume(instance_id=self.ec2_instance_id, volume_id=volume_id)
            self.utility.release_device(device=self.device, logger=self.logger, extra=self.extra)
            self.delete_volume(volume_id=volume_id)
            self.cleanup_directories(path)
            self.logger.error("Volume Unmount Failed", extra=self.extra)
            raise Exception("Volume Unmount Failed")
        # updating unmount info in DB
        if not self.utility.release_device_mount(device=self.device_m, logger=self.logger, extra=self.extra):
            self.detach_volume(instance_id=self.ec2_instance_id, volume_id=volume_id)
            self.utility.release_device(device=self.device, logger=self.logger, extra=self.extra)
            self.delete_volume(volume_id=volume_id)
            self.cleanup_directories(path)
            self.logger.error("Release Device Mount Failed", extra=self.extra)
            raise Exception("Release Device Mount Failed")
        # volume detach
        if not self.detach_volume(instance_id=self.ec2_instance_id, volume_id=volume_id):
            self.utility.release_device(device=self.device, logger=self.logger, extra=self.extra)
            self.delete_volume(volume_id=volume_id)
            self.cleanup_directories(path)
            self.logger.error("Detach Volume Failed", extra=self.extra)
            raise Exception("Detach Volume Failed")
        # updating release device status in DB attached during volume attach
        if not self.utility.release_device(device=self.device, logger=self.logger, extra=self.extra):
            self.delete_volume(volume_id=volume_id)
            self.cleanup_directories(path)
            self.logger.error("Release Device Failed", extra=self.extra)
            raise Exception("Release Device Failed")
        # deleted volume
        if not self.delete_volume(volume_id=volume_id):
            self.cleanup_directories(path)
            self.logger.error("Delete Volume Failed", extra=self.extra)
            raise Exception("Delete Volume Failed")
        # remove mounted path directory
        if not self.cleanup_directories(path):
            self.logger.error("Directory cleanup Failed", extra=self.extra)
            raise Exception("Directory cleanup Failed")

    def cleanup(self, instance_id, path, volume_id):
        """
        Cleanup
        :param instance_id: str
        :param path: str
        :param volume_id: atr
        :return:
        """
        self.unmount_volume()
        self.detach_volume(instance_id=instance_id, volume_id=volume_id)
        self.utility.release_device_mount(device=self.device_m, logger=self.logger, extra=self.extra)
        self.detach_volume(instance_id=instance_id, volume_id=volume_id)
        self.utility.release_device(device=self.device, logger=self.logger, extra=self.extra)
        self.delete_volume(volume_id=volume_id)
        self.cleanup_directories(path=path)

    def create_checksum_and_location(self, file_hash, mounted_path):
        """
        Create Checksum And Respective Directories
        :param file_hash:
        :param mounted_path:
        :return:
        """
        try:
            checksum = self.create_checksum(file_hash)
            checksum_location = os.path.join(mounted_path, 'tosend', checksum)
            os.makedirs(checksum_location)
            return checksum, checksum_location
        except Exception as e:
            self.logger.exception(str(e.args[0]) + "creating checksum and directory Failed", extra=self.extra)
            return False, False

    def cleanup_directories(self, path):
        """
        Cleanup All Directories recursively
        :param path: str
        :return:
        """
        try:
            command = "rm -rf {}".format(os.path.join(path, str(self.tenant_id)))
            return_code = subprocess.call([command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            return not bool(return_code)
        except Exception as e:
            self.logger.exception(str(e.args[0]) + "Directory Cleanup failed", extra=self.extra)
            return False

    @method_start_end
    def start(self):
        device_population_response = self.utility.all_devices(logger=self.logger, extra=self.extra)['device']
        if len(device_population_response) == 0:
            self.logger.error("Device Population was failed", extra=self.extra)
            raise Exception("Device Population was failed")
        if len(self.parse_args(sys.argv[1])) != 5:
            self.logger.error("script is executed with less parameters {}".format(str(sys.argv[1:])), extra=self.extra)
            raise Exception("script is executed with less parameters {}".format(str(sys.argv[1:])))
        self.tenant_id, self.scan_id, self.snapshot_data, self.bucket_name, self.instance_role = self.parse_args(sys.argv[1])
        self.extra.update({'scanId': str(self.scan_id), 'tenantId': str(self.tenant_id)})
        self.logger.debug("{}".format(device_population_response), extra=self.extra)
        for snapshot_id, instance_id in self.snapshot_data.items():
            self.logger.info("*" * 100, extra=self.extra)
            if not self.tenant_id or not self.scan_id or not snapshot_id or not instance_id or not self.bucket_name:
                self.logger.error("tenant_id: {}, scan_id: {}, snapshot_data: {} bucket_name: {} exiting!".format(self.tenant_id, self.scan_id, self.snapshot_data, self.bucket_name), extra=self.extra)
                raise Exception("tenant_id: {}, scan_id: {}, snapshot_data: {} bucket_name: {} exiting!".format(self.tenant_id, self.scan_id, self.snapshot_data, self.bucket_name))
            self.logger.info("Start Running Ec2 InstanceID: {} Tenant ID: {} ScanId: {} BucketName: {} snapshotID: {} instanceID: {}".format(self.ec2_instance_id, self.tenant_id, self.scan_id, self.bucket_name, snapshot_id, instance_id), extra=self.extra)
            self.main(instance_id=instance_id, snapshot_id=snapshot_id)
            self.logger.info("End Ec2 InstanceID: {} Tenant ID: {} ScanId: {} BucketName: {} snapshotID: {} instanceID: {}".format(self.ec2_instance_id, self.tenant_id, self.scan_id, self.bucket_name, snapshot_id, instance_id), extra=self.extra)


if __name__ == '__main__':
    if sys.argv[1] == '--help' or len(sys.argv) == 1:
        sys.exit(0)
    else:
        log = create_logger()
        utl = Utility()
        agentless = AgentLess(logger=log, utility=utl)
        agentless.start()

