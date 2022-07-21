# Agentless python support

## v1.0.0

### Tools
- Sqlite DB
- SQLAlchemy ORM

### Added or Updated
- Added Agentless python script.
- Updated requirement.txt file.
- Added tenantID and scanID prefix in each log lines
- retry in between calls changed to 3 sec
- Removed unnecessary tables from models

### Removed
- logging from imported modules like boto3, requests etc

### Install python dependencies
- pip3 install -r requirements.txt

## Mandatory utilities on linux
- lsblk should be installed. (By default it is already there on Ec2 machine)

### Running Agentless python Script through AWS SSM

- python3 agentless.py '{"scanId":609635,"tenantId":87686,"bucketName":"us-west-2-qaautoregression-cvs-bucket","snapshotData":{"snap-08885529e6a97c335":"i-08dfa17e9673920ad","snap-0af65c714a043c1bd":"i-04bf7ce3282eedc47"}}'
