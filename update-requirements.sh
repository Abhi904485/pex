#!/bin/bash -ex
poetry update
poetry export -f requirements.txt --without-hashes -o requirements.txt
poetry export --dev -f requirements.txt --without-hashes -o dev_requirements.txt
pushd shn_bin
poetry update
poetry export -f requirements.txt --without-hashes -o requirements.txt
poetry export --dev -f requirements.txt --without-hashes -o dev_requirements.txt
popd
