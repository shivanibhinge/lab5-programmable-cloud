#!/usr/bin/env python3

import time

import google.auth
import googleapiclient.discovery


credentials, project = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)

ZONE = "us-west1-b"
SOURCE_INSTANCE = "lab5-instance"
SNAPSHOT_NAME = f"base-snapshot-{SOURCE_INSTANCE}"

CLONE_NAMES = [
    "lab5-clone-1",
    "lab5-clone-2",
    "lab5-clone-3",
]

MACHINE_TYPE = "e2-micro"


def wait_for_zone_operation(compute, project, zone, operation_name):
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


def wait_for_global_operation(compute, project, operation_name):
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


def get_boot_disk_name(compute, project, zone, instance_name):
    instance = compute.instances().get(
        project=project,
        zone=zone,
        instance=instance_name
    ).execute()

    for disk in instance["disks"]:
        if disk.get("boot"):
            source = disk["source"]
            return source.split("/")[-1]

    raise RuntimeError("Boot disk not found.")


def create_snapshot(compute, project, zone, disk_name, snapshot_name):
    print(f"Creating snapshot: {snapshot_name}")

    body = {
        "name": snapshot_name
    }

    operation = compute.disks().createSnapshot(
        project=project,
        zone=zone,
        disk=disk_name,
        body=body
    ).execute()

    wait_for_zone_operation(
        compute,
        project,
        zone,
        operation["name"]
    )


def create_instance_from_snapshot(
    compute,
    project,
    zone,
    instance_name,
    snapshot_name
):
    print(f"Creating {instance_name}...")

    machine_type = f"zones/{zone}/machineTypes/{MACHINE_TYPE}"

    snapshot_url = (
        f"projects/{project}/global/snapshots/{snapshot_name}"
    )

    config = {
        "name": instance_name,

        "machineType": machine_type,

        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceSnapshot": snapshot_url
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
        ]
    }

    start_time = time.perf_counter()

    operation = compute.instances().insert(
        project=project,
        zone=zone,
        body=config
    ).execute()

    wait_for_zone_operation(
        compute,
        project,
        zone,
        operation["name"]
    )

    end_time = time.perf_counter()

    elapsed = end_time - start_time

    print(
        f"{instance_name} created in "
        f"{elapsed:.2f} seconds"
    )

    return elapsed


def main():
    print(f"Using project: {project}")

    print(
        f"Finding boot disk for instance: "
        f"{SOURCE_INSTANCE}"
    )

    disk_name = get_boot_disk_name(
        compute,
        project,
        ZONE,
        SOURCE_INSTANCE
    )

    print(f"Boot disk: {disk_name}")

    create_snapshot(
        compute,
        project,
        ZONE,
        disk_name,
        SNAPSHOT_NAME
    )

    print("Snapshot created successfully.")

    timings = []

    for clone_name in CLONE_NAMES:
        elapsed = create_instance_from_snapshot(
            compute,
            project,
            ZONE,
            clone_name,
            SNAPSHOT_NAME
        )

        timings.append(
            (clone_name, elapsed)
        )

    with open("TIMING.md", "w") as f:
        f.write("# VM Creation Timing\n\n")
        f.write(
            f"Snapshot used: `{SNAPSHOT_NAME}`\n\n"
        )

        for name, elapsed in timings:
            f.write(
                f"- `{name}`: "
                f"{elapsed:.2f} seconds\n"
            )

    print()
    print("Timing results written to TIMING.md")


if __name__ == "__main__":
    main()