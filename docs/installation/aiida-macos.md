# Install AiiDA on macOS

This creates an AiiDA profile with PostgreSQL storage, RabbitMQ messaging, and
a daemon for submitted processes.

## Install local services

Install [Homebrew](https://brew.sh/) first, then run:

```bash
brew install uv rabbitmq postgresql
brew services start rabbitmq
brew services start postgresql
```

## Create an isolated environment

```bash
uv venv --python 3.12 ~/.virtualenvs/aiida
source ~/.virtualenvs/aiida/bin/activate
uv pip install aiida-core
verdi --version
```

Run the remaining commands with this environment activated.

## Create a profile

```bash
verdi presto --profile-name goldilocks --use-postgres
```

`verdi presto` creates the profile, a default user, and a local computer. The
`--use-postgres` option asks it to create PostgreSQL storage instead of using
SQLite.

## Start AiiDA

```bash
verdi daemon start
verdi status
```

A healthy setup reports the profile, storage, broker, and daemon as available.

??? note "Optional RabbitMQ setting for long-running workflows"

    If local policy closes long-running consumers, add the following to the
    Homebrew RabbitMQ configuration and restart RabbitMQ:

    ```text
    consumer_timeout = 3600000000
    ```

    Treat this as a site policy, not a required AiiDA default.

For alternatives and current platform requirements, see the
[official AiiDA installation guide](https://aiida.readthedocs.io/projects/aiida-core/en/stable/installation/index.html).

Continue with [Quantum ESPRESSO and SCARF](qe-scarf.md).
