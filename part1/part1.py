#!/usr/bin/env python3

import time

import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError



credentials, project = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)


ZONE = "us-west1-b"
INSTANCE_NAME = "lab5-instance"
MACHINE_TYPE = "e2-medium"

FIREWALL_RULE = "allow-5000"
NETWORK_TAG = "allow-5000"


# waiting Compute Engine operation to finish

def wait_for_operation(compute, project, zone, operation_name):
    print(f"Waiting for operation {operation_name}...")

    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":
            if "error" in result:
                raise RuntimeError(result["error"])

            return result

        time.sleep(2)



STARTUP_SCRIPT = """#!/bin/bash

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

nohup flask run -h 0.0.0.0 > /var/log/flask.log 2>&1 &
"""


#vm creation

def create_instance(compute, project, zone, name):

    print(f"Creating VM: {name}")

    # Get the newest Ubuntu 22.04 image from the image family
    image_response = compute.images().getFromFamily(
        project="ubuntu-os-cloud",
        family="ubuntu-2204-lts"
    ).execute()

    source_image = image_response["selfLink"]

    machine_type = f"zones/{zone}/machineTypes/{MACHINE_TYPE}"

    config = {

        "name": name,

        "machineType": machine_type,

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
                        "type": "ONE_TO_ONE_NAT",
                        "name": "External NAT"
                    }
                ]
            }
        ],

        "metadata": {
            "items": [
                {
                    "key": "startup-script",
                    "value": STARTUP_SCRIPT
                }
            ]
        }
    }

    operation = compute.instances().insert(
        project=project,
        zone=zone,
        body=config
    ).execute()

    return operation


# Check firewall rule exists

def firewall_exists(compute, project, firewall_name):

    try:

        compute.firewalls().get(
            project=project,
            firewall=firewall_name
        ).execute()

        return True

    except HttpError as error:

        if error.resp.status == 404:
            return False

        raise


# Waiting for global operation

def wait_for_global_operation(compute, project, operation_name):

    print(f"Waiting for global operation {operation_name}...")

    while True:

        result = compute.globalOperations().get(
            project=project,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":

            if "error" in result:
                raise RuntimeError(result["error"])

            return result

        time.sleep(2)


# Create firewall rule

def create_firewall_rule(compute, project):

    print("Creating firewall rule allow-5000...")

    firewall_body = {

        "name": FIREWALL_RULE,

        "network": f"projects/{project}/global/networks/default",

        "direction": "INGRESS",

        "sourceRanges": [
            "0.0.0.0/0"
        ],

        "targetTags": [
            NETWORK_TAG
        ],

        "allowed": [
            {
                "IPProtocol": "tcp",
                "ports": [
                    "5000"
                ]
            }
        ]
    }

    operation = compute.firewalls().insert(
        project=project,
        body=firewall_body
    ).execute()

    wait_for_global_operation(
        compute,
        project,
        operation["name"]
    )


# Apply network tag

def set_instance_tag(compute, project, zone, instance_name):

    print("Applying network tag allow-5000...")

    instance = compute.instances().get(
        project=project,
        zone=zone,
        instance=instance_name
    ).execute()

    fingerprint = instance["tags"]["fingerprint"]

    tags_body = {
        "items": [
            NETWORK_TAG
        ],
        "fingerprint": fingerprint
    }

    operation = compute.instances().setTags(
        project=project,
        zone=zone,
        instance=instance_name,
        body=tags_body
    ).execute()

    wait_for_operation(
        compute,
        project,
        zone,
        operation["name"]
    )


# Get external IP


def get_external_ip(compute, project, zone, instance_name):

    instance = compute.instances().get(
        project=project,
        zone=zone,
        instance=instance_name
    ).execute()

    return (
        instance["networkInterfaces"][0]
        ["accessConfigs"][0]
        ["natIP"]
    )

# Main

def main():

    print(f"Using project: {project}")

    # Create VM
    operation = create_instance(
        compute,
        project,
        ZONE,
        INSTANCE_NAME
    )

    wait_for_operation(
        compute,
        project,
        ZONE,
        operation["name"]
    )

    print("VM created successfully.")

    # Firewall
    if firewall_exists(
        compute,
        project,
        FIREWALL_RULE
    ):

        print("Firewall rule already exists.")

    else:

        create_firewall_rule(
            compute,
            project
        )

    # Network tag
    set_instance_tag(
        compute,
        project,
        ZONE,
        INSTANCE_NAME
    )

    # Get public IP
    external_ip = get_external_ip(
        compute,
        project,
        ZONE,
        INSTANCE_NAME
    )

    print()
    print("VM setup completed.")
    print()
    print("Flask application should be available at:")
    print()
    print(f"http://{external_ip}:5000")
    print()


if __name__ == "__main__":
    main()