import os
from logging.handlers import RotatingFileHandler
import logging
import shnbin_common


def create_logger():
    # Create a custom logger
    logger_ = logging.getLogger('Agentless')
    # Removing unnecessary logging from s3transfer
    logging.getLogger('s3transfer').setLevel(logging.WARNING)
    # Adding Basic Config
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(tenantId)s - %(scanId)s - %(thread)d - %(threadName)s - %(process)d - %(levelname)s - %(lineno)d - %(message)s')

    # Console Logging
    # c_handler = logging.StreamHandler()
    # c_handler.setLevel(logging.DEBUG)
    # c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # c_handler.setFormatter(c_format)
    # logger_.addHandler(c_handler)

    # File Rotation Logging
    rotating_file_handler = RotatingFileHandler(os.path.join(shnbin_common.get_app_data_path(), "execution.log"), backupCount=10, maxBytes=10000000)
    rotating_file_handler.setLevel(logging.INFO)
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(tenantId)s - %(scanId)s - %(thread)d - %(threadName)s - %(process)d - %(levelname)s - %(lineno)d - %(message)s')
    rotating_file_handler.setFormatter(f_format)
    logger_.addHandler(rotating_file_handler)
    return logger_
