# openIMIS Backend Mobile reference module

This repository holds the files of the OpenIMIS Backend Mobile reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)


## Requirements

```bash
pip install -r requirements.txt
```

For development, you also need to run the following:
```
pip install -r requirements-dev.txt
```

## Installation

```bash
pip install -e .
```

with the development requirements

```bash
pip install -e .[dev]
```

## Tests

The tests can be run either with a standard pytest test harness or with the
one of the core module. In the first case, it's isolated and doesn't
require anything else that the present repo:

```bash
pytest
```

In the second one, you need to download the core project (and prepare the test
database), install the controls module in it `pip install -e <path to the
controls module>`, then you can run the tests:

```bash
python manage.py test --keep mobile
```


## ORM mapping

| Database table name | Django Model |
| - | - |
| `tblControls` | `Control` |

## Listened Django Signals

None

## Services

None

## Reports (template can be overloaded via report.ReportDefinition)

None

## GraphQL Queries

* `control`
* `control_str`: full text search on Control name, usage, and adjustability

An example:

```gql
{
  control{
    edges{
      node{
        name
      }
    }
  }
}
```

## GraphQL Mutations - each mutation emits default signals and return standard error lists (cfr. openimis-be-core_py)

None

## Configuration options (can be changed via core.ModuleConfiguration)

None

## openIMIS Modules Dependencies

None