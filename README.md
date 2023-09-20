# azure-resource-reaper

![Azure Functions](https://img.shields.io/badge/Azure%20Functions-v4-blue.svg) ![Azure](https://img.shields.io/badge/Azure-Resource%20Deletion-green.svg)

This Azure Function is a time-triggered function designed to automatically
delete Azure resources based on a specific lifetime tag. It helps manage and
clean up resources that are no longer needed, saving costs and improving
resource management in any Azure environment.

## Table of Contents
- [Overview](#overview)
- [Setup](#setup)
- [Configuration](#configuration)
- [Development](#configuration)
- [Contributing](#contributing)
- [License](#license)

## Overview

Azure resources can accumulate over time, leading to increased costs and
potential security risks. To mitigate this, this Azure Function provides a
solution for automatic resource deletion based on a `lifetime` tag that can
be assigned to resources.

The `lifetime` tag format is a succession of `<value><unit>` stanzas where
`<value>` is an integer and `<unit>` is one of the following:
    - y: years
    - mo: months
    - d: days
    - h: hours
    - m: minutes

## Setup

To deploy and use the function, follow the instructions in [Create a Python function in Azure from the command line](https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-cli-python).

## Configuration

The timer string for the `reap_resources` function can be configured in the `@app.schedule` decorator call via the [NCRONTAB](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer?tabs=python-v2%2Cin-process%2Cnodejs-v4&pivots=programming-language-python#ncrontab-expressions) expression. Additionally, a subscription ID must be set in the `AZURE_SUBSCRIPTION_ID` variable.

## Development

In order to develop on the function, the following are required:
- An Azure account with an active subscription.
- A [Python version supported by Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/supported-languages#languages-by-runtime-version).
- The [Azurite storage emulator](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite?tabs=npm#install-azurite).

Note that by using production credentials the function can delete resources from your environment!

## Contributing

It is required to sign the [Contributor Licence Agreement](https://ubuntu.com/legal/contributors) in order to contribute to this project.

An automated test is executed on PRs to check if it has been accepted.

## License

This project is covered by the [MIT License](https://github.com/ubuntu/azure-resource-reaper/blob/main/LICENSE).
