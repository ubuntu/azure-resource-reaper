"""
This is a Python Azure Function that will delete resources that have passed a certain lifetime.

The lifetime is defined by a tag on the resource. The tag is called "lifetime"
and is a succession of "<value><unit>" stanzas where <value> is an integer and
<unit> is one of the following:
    - y: years
    - mo: months
    - d: days
    - h: hours
    - m: minutes

The function will run on a schedule and will delete all resources that have passed their lifetime.
Resources that do not have the lifetime tag will be skipped entirely.
"""

import datetime
import logging
import os
import re

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

app = func.FunctionApp()

@app.function_name(name="reap_resources")
@app.schedule(schedule="0 0 * * * *",
              arg_name="timer",
              run_on_startup=True)
def reap_resources(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.info('The timer is past due.')

    # Acquire a credential object
    credential = DefaultAzureCredential()
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]

    # Initialize the resource client
    resource_client = ResourceManagementClient(credential, subscription_id)

    resources_deleted = 0
    provider_api_version_list = {}
    resource_groups = resource_client.resource_groups.list()
    for resource_group in resource_groups:
        # Cannot filter by tag here as we are requesting the additional createdTime property
        try:
            resources = resource_client.resources.list_by_resource_group(resource_group.name, expand='createdTime')
        except Exception as e:
            logging.error('Error getting resources for resource group "%s": %s', resource_group.name, e)
            continue

        for resource in resources:
            tags = resource.tags
            # Skip resources without tags
            if tags is None:
                continue
            # Skip resources without lifetime tag
            if 'lifetime' not in tags:
                continue

            # Parse lifetime tag
            lifetime = datetime_with_lifetime(resource.created_time, tags['lifetime'])

            # Check if resource is older than lifetime
            if datetime.datetime.now() < lifetime:
                continue

            logging.info('Resource %s is older than lifetime %s', resource.name, lifetime)

            if resource.managed_by is not None:
                logging.info('Resource %s is managed by %s - it will be deleted in the next function run, after the parent resource', resource.name, resource.managed_by)
                continue

            # Delete resource
            if not resource.type in provider_api_version_list:
                provider_api_version_list[resource.type] = api_version_for_resource_type(resource.type, resource_client)

            if provider_api_version_list[resource.type] is None:
                logging.warning('Could not find API version for resource "%s" of type "%s" - not deleting resource', resource.id, resource.type)
                continue

            try:
                poller = resource_client.resources.begin_delete_by_id(resource.id, api_version=provider_api_version_list[resource.type])
                poller.result()
            except Exception as e:
                logging.error('Error deleting resource "%s": %s', resource.id, e)
                continue

            logging.info('Resource %s deleted', resource.name)
            resources_deleted += 1

    logging.info('Deleted %d resources', resources_deleted)

def datetime_with_lifetime(created_time: datetime.datetime, lifetime: str) -> datetime.datetime:
    """
    Parse the lifetime tag and return a naive datetime object using the creation
    time of the resource as reference.
    """

    # Define conversion factors
    time_units = {
        'y': 365.25 * 24 * 60,  # Average days per year
        'mo': 30.44 * 24 * 60,  # Average days per month
        'd': 24 * 60,           # Days
        'h': 60,                # Hours
        'm': 1                  # Minutes
    }

    # Use regular expression to match and extract values and units
    pattern = r'(\d+)\s*([a-zA-Z]+)'
    matches = re.findall(pattern, lifetime)

    total_minutes = 0

    for value, unit in matches:
        if unit in time_units:
            total_minutes += int(value) * time_units[unit]

    return created_time + datetime.timedelta(minutes=total_minutes)

def api_version_for_resource_type(resource_type: str, resource_client: ResourceManagementClient) -> str | None:
    """
    Returns the latest API version for the given resource type.
    """

    namespace, rtype = resource_type.split('/')

    try:
        provider = resource_client.providers.get(namespace)
    except Exception as e:
        logging.error('Error getting provider for namespace "%s": %s', namespace, e)
        return None

    for resource in provider.resource_types:
        if not resource.resource_type == rtype:
            continue
        if len(resource.api_versions) < 1:
            continue
        return resource.api_versions[0]

    return None
