#!/usr/bin/env python3

import time

import google.auth
import googleapiclient.discovery


PROJECT = "lab-2-507501"
ZONE = "us-west1-b"

VM1_NAME = "lab5-controller"
VM2_NAME = "lab5-appliance"

MACHINE_TYPE = "e2-micro"

SERVICE_ACCOUNT_EMAIL = (
    "lab5-vm-creator@lab-2-507501.iam.gserviceaccount.com"
)

NETWORK_TAG = "allow-5000"


credentials, _ = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)


def wait_for_zone_operation(operation_name):
    print(f"Waiting for operation {operation_name}...")

    while True:
        result = compute.zoneOperations().get(
            project=PROJECT,
            zone=ZONE,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":

            if "error" in result:
                raise RuntimeError(result["error"])

            return result

        time.sleep(2)


VM2_STARTUP_SCRIPT = r"""#!/bin/bash

set -e

mkdir -p /opt/lab5
cd /opt/lab5

apt-get update
apt-get install -y python3 python3-pip git

git clone https://github.com/cu-csci-4253-datacenter/flask-tutorial

cd flask-tutorial

python3 setup.py install
pip3 install -e .

export FLASK_APP=flaskr

flask init-db

nohup flask run -h 0.0.0.0 \
    > /var/log/flask.log 2>&1 &
"""


VM1_LAUNCH_CODE = r'''
import time

import google.auth
import googleapiclient.discovery


PROJECT = "lab-2-507501"
ZONE = "us-west1-b"

VM2_NAME = "lab5-appliance"
MACHINE_TYPE = "e2-micro"

NETWORK_TAG = "allow-5000"


credentials, _ = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)


def wait_for_operation(operation_name):

    while True:

        result = compute.zoneOperations().get(
            project=PROJECT,
            zone=ZONE,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":

            if "error" in result:
                raise RuntimeError(result["error"])

            return

        time.sleep(2)


with open(
    "/srv/vm2-startup-script.sh",
    "r"
) as f:
    vm2_startup_script = f.read()


image = compute.images().getFromFamily(
    project="ubuntu-os-cloud",
    family="ubuntu-2204-lts"
).execute()

source_image = image["selfLink"]


config = {

    "name": VM2_NAME,

    "machineType":
        f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",

    "tags": {
        "items": [
            NETWORK_TAG
        ]
    },

    "disks": [
        {
            "boot": True,
            "autoDelete": True,

            "initializeParams": {
                "sourceImage": source_image
            }
        }
    ],

    "networkInterfaces": [
        {
            "network": "global/networks/default",

            "accessConfigs": [
                {
                    "name": "External NAT",
                    "type": "ONE_TO_ONE_NAT"
                }
            ]
        }
    ],

    "metadata": {
        "items": [
            {
                "key": "startup-script",
                "value": vm2_startup_script
            }
        ]
    }
}


print("VM-1 is creating VM-2...")


operation = compute.instances().insert(
    project=PROJECT,
    zone=ZONE,
    body=config
).execute()


wait_for_operation(
    operation["name"]
)


vm2 = compute.instances().get(
    project=PROJECT,
    zone=ZONE,
    instance=VM2_NAME
).execute()


external_ip = (
    vm2["networkInterfaces"][0]
       ["accessConfigs"][0]
       ["natIP"]
)


print("VM-2 created successfully.")
print(
    f"Flask should be available at "
    f"http://{external_ip}:5000"
)
'''


VM1_STARTUP_SCRIPT = r"""#!/bin/bash

set -e

mkdir -p /srv
cd /srv

apt-get update
apt-get install -y python3 python3-pip curl

curl \
  -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/vm2-startup-script \
  > /srv/vm2-startup-script.sh

curl \
  -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/vm1-launch-code \
  > /srv/vm1-launch-code.py

pip3 install \
  google-api-python-client \
  google-auth

python3 /srv/vm1-launch-code.py \
  > /var/log/vm1-launch.log 2>&1
"""


def create_vm1():

    print(
        f"Creating controller VM: "
        f"{VM1_NAME}"
    )

    image = compute.images().getFromFamily(
        project="ubuntu-os-cloud",
        family="ubuntu-2204-lts"
    ).execute()

    source_image = image["selfLink"]

    config = {

        "name": VM1_NAME,

        "machineType":
            f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",

        "disks": [
            {
                "boot": True,
                "autoDelete": True,

                "initializeParams": {
                    "sourceImage": source_image
                }
            }
        ],

        "networkInterfaces": [
            {
                "network":
                    "global/networks/default",

                "accessConfigs": [
                    {
                        "name": "External NAT",
                        "type": "ONE_TO_ONE_NAT"
                    }
                ]
            }
        ],

        "serviceAccounts": [
            {
                "email":
                    SERVICE_ACCOUNT_EMAIL,

                "scopes": [
                    "https://www.googleapis.com/auth/cloud-platform"
                ]
            }
        ],

        "metadata": {

            "items": [

                {
                    "key":
                        "startup-script",

                    "value":
                        VM1_STARTUP_SCRIPT
                },

                {
                    "key":
                        "vm1-launch-code",

                    "value":
                        VM1_LAUNCH_CODE
                },

                {
                    "key":
                        "vm2-startup-script",

                    "value":
                        VM2_STARTUP_SCRIPT
                }
            ]
        }
    }


    operation = compute.instances().insert(
        project=PROJECT,
        zone=ZONE,
        body=config
    ).execute()


    wait_for_zone_operation(
        operation["name"]
    )


    print(
        "VM-1 created successfully."
    )

    print(
        "VM-1 will now create VM-2 "
        "using its attached service account."
    )


def main():

    create_vm1()

    print()
    print(
        "Wait about 1-3 minutes for "
        "VM-1 to launch VM-2."
    )

    print()

    print(
        "Check using:"
    )

    print(
        "gcloud compute instances list"
    )


if __name__ == "__main__":
    main()