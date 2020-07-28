"""Interfaces with database."""

from aioch import Client
from datetime import datetime
from iris.commons.subprocess import start_stream_subprocess


class Database(object):
    def __init__(self, host, logger=None):
        self.host = host
        self.logger = logger
        self.client = Client(self.host)

    async def create_datebase(self, database_name):
        """Create a database if not exists."""
        await self.client.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")

    async def drop_table(self, table_name):
        """Drop a table."""
        await self.client.execute(f"DROP TABLE IF EXISTS {table_name}")

    async def clean_table(self, table_name):
        """Clean a table."""
        await self.client.execute(f"ALTER TABLE {table_name} DELETE WHERE 1=1")

    async def disconnect(self):
        """Disconnect agent."""
        await self.client.disconnect()


class DatabaseAgents(Database):
    """Interface that handle agents history."""

    def __init__(self, host, table_name):
        super().__init__(host)
        self.table_name = table_name

    async def create_table(self, drop=False):
        """Create the table with all registered agents."""
        if drop:
            self.drop(self.table_name)

        await self.client.execute(
            f"CREATE TABLE IF NOT EXISTS {self.table_name}"
            "(uuid UUID, user String, version String, ip_address IPv4, "
            "probing_rate UInt32, buffer_sniffer_size UInt32, inf_born UInt32, "
            "sup_born UInt32, ips_per_subnet UInt32, pfring UInt8) "
            "ENGINE=MergeTree() "
            "ORDER BY (uuid)",
        )

    async def all(self, user="all"):
        """Get all measurements uuid for a given user."""
        responses = await self.client.execute(
            f"SELECT uuid FROM {self.table_name} WHERE user=%(user)s", {"user": user},
        )
        return [str(response[0]) for response in responses]

    async def get(self, uuid, user="all"):
        responses = await self.client.execute(
            f"SELECT * FROM {self.table_name} WHERE user=%(user)s AND uuid=%(uuid)s",
            {"user": user, "uuid": uuid},
        )
        try:
            response = responses[0]
        except IndexError:
            return None

        return {
            "uuid": str(response[0]),
            "user": response[1],
            "version": response[2],
            "ip_address": str(response[3]),
            "probing_rate": response[4],
            "buffer_sniffer_size": response[5],
            "inf_born": response[6],
            "sup_born": response[7],
            "ips_per_subnet": response[8],
            "pfring": bool(response[9]),
        }

    async def register(self, uuid, parameters):
        print(parameters)
        await self.client.execute(
            f"INSERT INTO {self.table_name} VALUES",
            [
                {
                    "uuid": uuid,
                    "user": "all",  # agents share for all user at the moment
                    "version": parameters["version"],
                    "ip_address": parameters["ip_address"],
                    "probing_rate": parameters["probing_rate"],
                    "buffer_sniffer_size": parameters["buffer_sniffer_size"],
                    "inf_born": parameters["inf_born"],
                    "sup_born": parameters["sup_born"],
                    "ips_per_subnet": parameters["ips_per_subnet"],
                    "pfring": bool(parameters["pfring"]),
                }
            ],
        )


class DatabaseMeasurements(Database):
    """Interface that handle measurements history."""

    def __init__(self, host, table_name):
        super().__init__(host)
        self.table_name = table_name

    async def create_table(self, drop=False):
        """Create the table with all registered measurements."""
        if drop:
            self.drop(self.table_name)

        await self.client.execute(
            f"CREATE TABLE IF NOT EXISTS {self.table_name}"
            "(uuid UUID, user String, agents Array(UUID), target_file_key String, "
            "protocol String, destination_port UInt16, min_ttl UInt8, max_ttl UInt8, "
            "start_time DateTime, "
            "end_time Nullable(DateTime)) "
            "ENGINE=MergeTree() "
            "ORDER BY (uuid)",
        )

    async def all(self, user):
        """Get all measurements uuid for a given user."""
        responses = await self.client.execute(
            f"SELECT uuid FROM {self.table_name} WHERE user=%(user)s", {"user": user},
        )
        return [str(response[0]) for response in responses]

    async def get(self, user, uuid):
        """Get all measurement information."""
        responses = await self.client.execute(
            f"SELECT * FROM {self.table_name} WHERE user=%(user)s AND uuid=%(uuid)s",
            {"user": user, "uuid": uuid},
        )
        try:
            response = responses[0]
        except IndexError:
            return None

        return {
            "uuid": str(response[0]),
            "user": response[1],
            "agents": [str(r) for r in response[2]],
            "target_file_key": response[3],
            "protocol": response[4],
            "destination_port": response[5],
            "min_ttl": response[6],
            "max_ttl": response[7],
            "start_time": response[8].isoformat(),
            "end_time": response[9].isoformat() if response[9] is not None else None,
        }

    async def register(self, agents, measurement_parameters):
        """Register a measurement."""
        await self.client.execute(
            f"INSERT INTO {self.table_name} VALUES",
            [
                {
                    "uuid": measurement_parameters["measurement_uuid"],
                    "user": measurement_parameters["user"],
                    "agents": agents,
                    "target_file_key": measurement_parameters["target_file_key"],
                    "protocol": measurement_parameters["protocol"],
                    "destination_port": measurement_parameters["destination_port"],
                    "min_ttl": measurement_parameters["min_ttl"],
                    "max_ttl": measurement_parameters["max_ttl"],
                    "start_time": datetime.fromtimestamp(
                        measurement_parameters["start_time"]
                    ),
                    "end_time": None,
                }
            ],
        )

    async def stamp_end_time(self, user, uuid, end_time):
        """Stamp the end time for a measurement."""
        await self.client.execute(
            f"ALTER TABLE {self.table_name} "
            "UPDATE end_time=toDateTime(%(end_time)s) "
            "WHERE user=%(user)s AND uuid=%(uuid)s",
            {"end_time": end_time, "user": user, "uuid": uuid},
        )


class DatabaseMeasurementResults(object):
    """Database interface to handle measurement results."""

    def __init__(self, host, logger=None):
        self.host = host
        self.logger = logger
        self.client = Client(self.host)

    @staticmethod
    def forge_table_name(
        measurement_uuid, agent_uuid,
    ):
        """Forge the table name from measurement UUID and agent UUID."""
        sanitized_measurement_uuid = measurement_uuid.replace("-", "_")
        sanitized_agent_uuid = agent_uuid.replace("-", "_")
        return (
            "results" + f"__{sanitized_measurement_uuid}" + f"__{sanitized_agent_uuid}"
        )

    @staticmethod
    def parse_table_name(table_name):
        """Parse table name to extract parameters."""
        table_name_split = table_name.split("__")
        measurement_uuid, agent_uuid = (
            table_name_split[1],
            table_name_split[2],
        )
        return {
            "measurement_uuid": measurement_uuid.replace("_", "-"),
            "agent_uuid": agent_uuid.replace("_", "-"),
        }

    async def create_table(self, table_name, drop=False):
        """Create a table."""
        if drop:
            self.drop(table_name)

        await self.client.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name}"
            "(src_ip UInt32, dst_prefix UInt32, dst_ip UInt32, reply_ip UInt32, "
            "proto UInt8, src_port UInt16, dst_port UInt16, ttl UInt8, "
            "ttl_from_udp_length UInt8, type UInt8, "
            "code UInt8, rtt Float64, reply_ttl UInt8, "
            "reply_size UInt16, round UInt32, snapshot UInt16) ENGINE=MergeTree() "
            "ORDER BY (src_ip, dst_prefix, dst_ip, ttl, src_port, dst_port, snapshot)",
        )

    async def insert_csv(self, csv_filepath, table_name):
        """Insert CSV file into table."""
        # We could avoid using clickhouse-client for that,
        # but since we have it for the Reader, why not, at the moment.
        cmd = (
            "cat "
            + str(csv_filepath)
            + " | clickhouse-client --max_insert_block_size=100000 --host="
            + self.host
            + " --query='INSERT INTO "
            + str(table_name)
            + " FORMAT CSV'"
        )

        await start_stream_subprocess(cmd, logger=self.logger)
