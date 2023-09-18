import datetime
import logging
import os
import unittest

from collections import namedtuple
from unittest.mock import patch, call

from function_app import reap_resources, datetime_with_lifetime

ResourceGroup = namedtuple('ResourceGroup', ['name'])
Resource = namedtuple('Resource', ['id', 'name', 'tags', 'created_time', 'managed_by', 'type'])
Provider = namedtuple('Provider', ['namespace', 'resource_types'])
ProviderResourceType = namedtuple('ProviderResourceType', ['resource_type', 'api_versions'])

class MockTimer():
    def __init__(self):
        self.past_due = True

@patch.dict(os.environ, {'AZURE_SUBSCRIPTION_ID': '12345678-1234-1234-1234-123456789012'})
class TestFunction(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

        datetime_at_creation = datetime.datetime(2023, 9, 14, 11, 0, tzinfo=datetime.timezone.utc)
        patcher = patch('function_app.ResourceManagementClient', autospec=True)
        self.addCleanup(patcher.stop)
        self.mock_resource_client = patcher.start().return_value
        self.mock_resource_client.resources.list_by_resource_group.side_effect = lambda rg, **kwargs: {
            'rg1': [
                Resource(id='rg1nic1', name='rg1nic1', type='Microsoft.Network/networkInterfaces', tags={'lifetime': '12h 30m'}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg1nic2', name='rg1nic2', type='Microsoft.Network/networkInterfaces', tags={'lifetime': '30m'}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg1vm1', name='rg1vm1', type='Microsoft.Compute/virtualMachines', tags={'lifetime': '1h 12m'}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg1disk1', name='rg1disk1', type='Microsoft.Compute/disks', tags={'lifetime': '10m'}, managed_by="some_other_resource", created_time=datetime_at_creation),
                Resource(id='rg1noapi', name='rg1noapi', type='Microsoft.Network/noApiVersion', tags={'lifetime': '5m'}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg1noprovider', name='rg1noprovider', type='Microsoft.Network/noProvider', tags={'lifetime': '1h 1m'}, managed_by=None, created_time=datetime_at_creation),
            ],
            'rg2': [
                Resource(id='rg2notag', name='rg2notag', type='Microsoft.Network/networkInterfaces', tags={}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg2notags', name='rg2notags', type='Microsoft.Network/networkInterfaces', tags=None, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg2nic1', name='rg2nic1', type='Microsoft.Network/networkInterfaces', tags={'lifetime': '100d'}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg2vm1', name='rg2vm1', type='Microsoft.Compute/virtualMachines', tags={'lifetime': '3h 30m'}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg2vm2', name='rg2vm2', type='Microsoft.Compute/virtualMachines', tags={'lifetime': 'not parsable'}, managed_by=None, created_time=datetime_at_creation),
                Resource(id='rg2vm3', name='rg2vm3', type='Microsoft.Compute/virtualMachines', tags={'lifetime': '1h'}, managed_by=None, created_time=datetime_at_creation),
            ],
            'rg3': [
                Resource(id='rg3res1', name='rg3res1', type='Microsoft.Network/networkInterfaces', tags={'lifetime': '1m'}, managed_by=None, created_time=datetime_at_creation),
            ],
        }[rg]

        datetime_to_patch = datetime.datetime(2023, 9, 14, 12, 40, tzinfo=datetime.timezone.utc)
        datetime_patcher = patch('datetime.datetime', wraps=datetime.datetime)
        self.addCleanup(datetime_patcher.stop)
        self.mock_datetime = datetime_patcher.start()
        self.mock_datetime.now.return_value = datetime_to_patch

    def test_reap_resources(self):
        # Set up the mocks
        self.mock_resource_client.resource_groups.list.return_value = [
            ResourceGroup(name='rg1'),
            ResourceGroup(name='rg2'),
        ]
        self.mock_resource_client.providers.get.side_effect = lambda namespace: {
            'Microsoft.Network': Provider(namespace='Microsoft.Network', resource_types=[
                ProviderResourceType(resource_type='networkInterfaces', api_versions=['2020-08-01', '2020-07-01']),
                ProviderResourceType(resource_type='noApiVersion', api_versions=[]),
            ]),
            'Microsoft.Compute': Provider(namespace='Microsoft.Compute', resource_types=[
                ProviderResourceType(resource_type='virtualMachines', api_versions=['2020-09-01', '2020-07-01']),
                ProviderResourceType(resource_type='disks', api_versions=['2020-10-01', '2020-07-01']),
            ]),
        }[namespace]

        # Construct a mock timer
        timer = MockTimer()
        func_call = reap_resources.build().get_user_function()
        resp = func_call(timer)

        # Check the output
        self.assertIsNone(resp)

        # Check the calls
        self.mock_resource_client.resources.begin_delete_by_id.assert_has_calls([
            call('rg1nic2', api_version='2020-08-01'),
            call('rg1vm1', api_version='2020-09-01'),
            call('rg2vm3', api_version='2020-09-01'),
        ], any_order=True)

    def test_reap_resources_with_resource_group_error(self):
        # Set up the mocks
        self.mock_resource_client.resource_groups.list.return_value = [
            ResourceGroup(name='badrg'),
            ResourceGroup(name='rg2'),
        ]
        self.mock_resource_client.providers.get.side_effect = lambda namespace: {
            'Microsoft.Network': Provider(namespace='Microsoft.Network', resource_types=[
                ProviderResourceType(resource_type='networkInterfaces', api_versions=['2020-08-01', '2020-07-01']),
                ProviderResourceType(resource_type='noApiVersion', api_versions=[]),
            ]),
            'Microsoft.Compute': Provider(namespace='Microsoft.Compute', resource_types=[
                ProviderResourceType(resource_type='virtualMachines', api_versions=['2020-09-01', '2020-07-01']),
                ProviderResourceType(resource_type='disks', api_versions=['2020-10-01', '2020-07-01']),
            ]),
        }[namespace]

        # Construct a mock timer
        timer = MockTimer()
        func_call = reap_resources.build().get_user_function()
        resp = func_call(timer)

        # Check the output
        self.assertIsNone(resp)

        # Check the calls
        self.mock_resource_client.resources.begin_delete_by_id.assert_has_calls([
            call('rg2vm3', api_version='2020-09-01'),
        ], any_order=True)

    def test_reap_resources_with_resource_delete_error(self):
        # Set up the mocks
        self.mock_resource_client.resource_groups.list.return_value = [
            ResourceGroup(name='rg1'),
            ResourceGroup(name='rg2'),
        ]
        self.mock_resource_client.providers.get.side_effect = lambda namespace: {
            'Microsoft.Network': Provider(namespace='Microsoft.Network', resource_types=[
                ProviderResourceType(resource_type='networkInterfaces', api_versions=['2020-08-01', '2020-07-01']),
                ProviderResourceType(resource_type='noApiVersion', api_versions=[]),
            ]),
            'Microsoft.Compute': Provider(namespace='Microsoft.Compute', resource_types=[
                ProviderResourceType(resource_type='virtualMachines', api_versions=['2020-09-01', '2020-07-01']),
                ProviderResourceType(resource_type='disks', api_versions=['2020-10-01', '2020-07-01']),
            ]),
        }[namespace]

        self.mock_resource_client.resources.begin_delete_by_id.side_effect = lambda id, **kwargs: {
            'rg1nic2': Exception('failed to delete resource'),
            'rg1vm1': None,
            'rg2vm3': Exception('failed to delete resource'),
        }[id]

        # Construct a mock timer
        timer = MockTimer()
        func_call = reap_resources.build().get_user_function()
        resp = func_call(timer)

        # Check the output
        self.assertIsNone(resp)

        # Check the calls
        self.mock_resource_client.resources.begin_delete_by_id.assert_has_calls([
            call('rg1vm1', api_version='2020-09-01'),
        ], any_order=True)

    def test_reap_resources_with_provider_error(self):
        # Set up the mocks
        self.mock_resource_client.resource_groups.list.return_value = [
            ResourceGroup(name='rg1'),
            ResourceGroup(name='rg2'),
        ]
        self.mock_resource_client.providers.get.side_effect = lambda namespace: {
            'Microsoft.Compute': Provider(namespace='Microsoft.Compute', resource_types=[
                ProviderResourceType(resource_type='virtualMachines', api_versions=['2020-09-01', '2020-07-01']),
                ProviderResourceType(resource_type='disks', api_versions=['2020-10-01', '2020-07-01']),
            ]),
        }[namespace]

        # Construct a mock timer
        timer = MockTimer()
        func_call = reap_resources.build().get_user_function()
        resp = func_call(timer)

        # Check the output
        self.assertIsNone(resp)

        # Check the calls
        self.mock_resource_client.resources.begin_delete_by_id.assert_has_calls([
            call('rg2vm3', api_version='2020-09-01'),
        ], any_order=True)

    def test_reap_resources_with_no_subscription_id(self):
        del os.environ['AZURE_SUBSCRIPTION_ID']

        # Construct a mock timer
        timer = MockTimer()
        func_call = reap_resources.build().get_user_function()

        with self.assertRaises(KeyError):
            func_call(timer)

        # Confirm we didn't call the resource client
        self.mock_resource_client.assert_not_called()


class TestLifetimeParser(unittest.TestCase):
    def test_lifetime_parser(self):
        created_time = datetime.datetime(2023, 9, 14, 11, 0)

        self.assertEqual(datetime_with_lifetime(created_time, '1h'), datetime.datetime(2023, 9, 14, 12, 0))
        self.assertEqual(datetime_with_lifetime(created_time, '1h 30m'), datetime.datetime(2023, 9, 14, 12, 30))
        self.assertEqual(datetime_with_lifetime(created_time, '1d'), datetime.datetime(2023, 9, 15, 11, 0))
        self.assertEqual(datetime_with_lifetime(created_time, '1d 1h'), datetime.datetime(2023, 9, 15, 12, 0))
        self.assertEqual(datetime_with_lifetime(created_time, '1d 1h 30m'), datetime.datetime(2023, 9, 15, 12, 30))
        self.assertEqual(datetime_with_lifetime(created_time, '1mo'), datetime.datetime(2023, 10, 14, 21, 33, 36))
        self.assertEqual(datetime_with_lifetime(created_time, '1y'), datetime.datetime(2024, 9, 13, 17, 0))
        self.assertEqual(datetime_with_lifetime(created_time, '1h 1h 1h'), datetime.datetime(2023, 9, 14, 14, 0))
