import os

from sqlalchemy import Column, String, BOOLEAN
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlalchemy as sa
import shnbin_common

CURRENT_DIRECTORY_PATH = os.path.dirname(__file__)
SQLALCHEMY_DATABASE_URI = "sqlite:////{}".format(os.path.join(shnbin_common.get_app_data_path(), 'devices.db'))
engine = sa.create_engine(SQLALCHEMY_DATABASE_URI, echo=True)
Base = declarative_base()

Session = sessionmaker(bind=engine)
Session.configure(bind=engine)
session = Session()


class Device(Base):
    __tablename__ = "device"
    value = Column(String(100), primary_key=True, nullable=False, unique=True)
    status = Column(BOOLEAN, nullable=False, unique=False)

    def __init__(self, value=None, status=None):
        self.value = value
        self.status = status

    def __repr__(self):
        return f"{self.__class__.__name__}(value = {self.value})(status = {self.status})"


class DeviceMount(Base):
    __tablename__ = "deviceMount"
    value = Column(String(100), primary_key=True, nullable=False, unique=True)
    status = Column(BOOLEAN, nullable=False, unique=False)

    def __init__(self, value=None, status=None):
        self.value = value
        self.status = status

    def __repr__(self):
        return f"{self.__class__.__name__}(value = {self.value})(status = {self.status})"


Base.metadata.create_all(engine)
