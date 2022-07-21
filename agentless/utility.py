import time

from blkinfo import BlkDiskInfo

from agentless.model import session, Device, DeviceMount
from sqlalchemy.exc import IntegrityError, NoResultFound, SQLAlchemyError, MultipleResultsFound, NoSuchTableError, DataError, DatabaseError
import threading


class Utility:

    def __init__(self):
        self.lock = threading.Lock()

    def all_devices(self, logger, extra):
        """
        Get All Available Devices
        :return: dict
        """
        try:
            devices = session.query(Device).all()
        except (DataError, DatabaseError, NoSuchTableError, NoResultFound, SQLAlchemyError) as e:
            logger.error("there was some while querying table {}".format(e))
            return {'devices': []}
        if len(devices) > 0:
            logger.info("Devices already populated {}".format(devices), extra=extra)
            return {'device': [(device.value, device.status) for device in devices]}
        else:
            with self.lock:
                for i in 'fghijklmnop':
                    device = Device(value=('/dev/sd{}'.format(i)), status=True)
                    try:
                        session.add(device)
                        session.commit()
                    except IntegrityError as e:
                        logger.error("trying to insert duplicate Entries {}".format(e), extra=extra)
                        return {'device': "Device Population Failed! trying to insert duplicate Entries"}
                logger.info("Device Population Successful", extra=extra)
                return {'device': "Device Population Successful"}

    def get_device_mount(self, logger, extra):
        """
        Get Device Mount
        :param extra: dict
        :param logger: obj
        :return:
        """
        with self.lock:
            count = 0
            device = self.mount_point(logger=logger, extra=extra)
            count += 1
            while not device:
                time.sleep(2)
                device = self.mount_point(logger=logger, extra=extra)
                count += 1
                if count == 20:
                    return {'device': False}
            else:
                return {'device': device}

    @staticmethod
    def check_if_device_already_present(value, logger, extra):
        """
        Check if device is already mounted
        :param extra: dict
        :param logger: obj
        :param value: str
        :return: bool
        """
        try:
            device_mount = session.query(DeviceMount).filter_by(value=value).one_or_none()
            if device_mount:
                logger.info("Device {} status is {}".format(device_mount.value, "Free" if device_mount.status else "In Used"), extra=extra)
                return device_mount, device_mount.status
            else:
                logger.info("Device is free for mount", extra=extra)
                return False, False
        except MultipleResultsFound as e:
            logger.error("Multiple Result Found {}".format(e), extra=extra)
            return False

    def mount_point(self, logger, extra):
        """
        Get dynamic device name after volume attach
        :param extra: dict
        :param logger: obj
        :return:
        """
        for device in BlkDiskInfo().get_disks():
            if device['children']:
                for child_device in device['children']:
                    if child_device['type'] == 'part' and child_device['mountpoint'] == "" and child_device['fstype']:
                        device_name = "/dev/{}".format(child_device['name'])
                        device_mount, status = self.check_if_device_already_present(value=device_name, logger=logger, extra=extra)
                        if not device_mount:
                            try:
                                device_ = DeviceMount(value=device_name, status=False)
                                session.add(device_)
                                session.commit()
                                logger.info("dynamic device name {} after volume attach".format(device_.value), extra=extra)
                                return device_.value
                            except IntegrityError as e:
                                logger.error("trying to insert duplicate Entries {}".format(e), extra=extra)
                                session.rollback()
                                return False
                        if not status:
                            continue
                        device_mount.status = False
                        session.add(device_mount)
                        session.commit()
                        return device_mount.value
        else:
            return False

    def release_device_mount(self, device, logger, extra):
        """
        Release Mounted Device
        :return: bool
        """
        with self.lock:
            try:
                device_mount = session.query(DeviceMount).filter_by(value=device, status=False).one_or_none()
                if device_mount:
                    device_mount.status = True
                    session.add(device_mount)
                    session.commit()
                    logger.info("Mounted Device {} released".format(device_mount.value), extra=extra)
                    return True
                else:
                    logger.error("Mounted Device {} release failed ".format(device), extra=extra)
                    return False
            except (MultipleResultsFound, SQLAlchemyError) as e:
                logger.error("Multiple Result Found {}".format(e), extra=extra)
                return False

    def get_device(self, logger, extra):
        """
        Get Device
        :return: dict
        """
        with self.lock:
            device = session.query(Device).filter_by(status=True).first()
            if device:
                try:
                    device.status = False
                    session.add(device)
                    session.commit()
                    logger.info("Get Device {} was successful".format(device.value), extra=extra)
                    return {'device': device.value}
                except SQLAlchemyError as e:
                    logger.error("device addition and deletion failed {}".format(e), extra=extra)
                    return {'device': False}
            else:
                return {'device': False}

    def release_device(self, device, logger, extra):
        """
        Release Device
        :return: bool
        """
        with self.lock:
            try:
                device_ = session.query(Device).filter_by(value=device, status=False).one_or_none()
                if device_:
                    device_.status = True
                    session.add(device_)
                    session.commit()
                    logger.info("Release Device {} was successful".format(device_.value), extra=extra)
                    return True
                else:
                    logger.error("Device {} Release failed".format(device), extra=extra)
                    return False
            except (SQLAlchemyError, MultipleResultsFound) as e:
                logger.error("device release failed {}".format(e), extra=extra)
                return False
