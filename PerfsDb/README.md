Performance Db tests
====================

Introduction
------------

This project performs benchmark tests of Orthanc with its various DB servers.

It can be used to:

- compare DB servers performance
- compare performance between small and big DB
- test the effectiveness of some code refactoring

In a first step, the project creates a set of DB servers and populates them.
Then, it will perform a set of basic operations on Orthanc with each of these servers
and measure the time required for each operation.

Timings are measured at the API level.  Since we want to measure mainly the DB performance,
we'll mainly use very small DICOM files (without pixels data).

Prerequisites
-------------

- install standard tools
```bash
sudo apt-get install -y mercurial wget curl
```

- install python3, pip3 and pipenv

```bash
sudo apt-get install -y python3 python3-pip python3-venv
```

- [install Docker-CE](https://docs.docker.com/install/linux/docker-ce/ubuntu/#set-up-the-repository)
- have access to docker without typing `sudo`.  This is done by typing: `sudo groupadd docker` and `sudo usermod -aG docker $USER`
- have Orthanc and its DB plugins natively installed or compiled on your host system

Once all prerequisites are installed, you should always execute all commands from a python virtual-env.  To initialize the virtual env the first time:

```bash
python3 -m venv .env
source .env/bin/activate
pip install -r requirements.txt
```

To enter the virtual-env the next times:

```bash
source .env/bin/activate
```

Initializing a DB before tests
-----------------

```bash
python Run.py --orthanc-path=/home/amazy/builds/orthanc-build-release/ --plugins-path=/home/amazy/builds/mysql-release/ --init --mysql-tiny
```

Clearing a DB
-----------------

```bash
python Run.py --orthanc-path=/home/amazy/builds/orthanc-build-release/ --plugins-path=/home/amazy/builds/mysql-release/ --clear --mysql-tiny
```

Runing tests on multiple DBs
-----------------

```bash
python Run.py --orthanc-path=/home/amazy/builds/orthanc-build-release/ --plugins-path=/home/amazy/builds/orthanc-build-release/ --run --pg9-tiny --pg10-tiny --pg11-tiny --mysql-tiny --sqlite-tiny --mssql-tiny

python Run.py --orthanc-path=/data/orthanc-binaries/ --plugins-path=/data/orthanc-binaries/ --run --pg9-tiny --pg10-tiny --pg11-tiny --mysql-tiny --sqlite-tiny --mssql-tiny

```
