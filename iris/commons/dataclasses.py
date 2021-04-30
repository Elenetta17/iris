class ParametersDataclass(object):
    def __init__(
        self,
        agent_uuid,
        measurement_parameters,
        physical_parameters,
        specific_parameters,
    ):
        self.measurement_parameters = measurement_parameters
        self.physical_parameters = physical_parameters
        self.specific_parameters = specific_parameters
        self._dataclass = {
            **physical_parameters,
            **measurement_parameters,
            **specific_parameters,
            **{"agent_uuid": agent_uuid},
        }

    def __getattr__(self, parameter):
        exception = AttributeError(f"`{parameter}` not found in dataclass")
        if parameter == "_dataclass":
            raise exception
        try:
            return self._dataclass[parameter]
        except KeyError:
            raise exception

    @staticmethod
    def from_request(request):
        parameters = request["parameters"]
        return ParametersDataclass(
            parameters["agent_uuid"],
            {
                "tool": parameters["tool"],
                "measurement_uuid": parameters["measurement_uuid"],
                "user": parameters["user"],
                "tags": parameters["tags"],
                "start_time": parameters["start_time"],
            },
            {
                "user": parameters["user"],
                "version": parameters["version"],
                "hostname": parameters["hostname"],
                "ip_address": parameters["ip_address"],
                "min_ttl": parameters["min_ttl"],
                "max_probing_rate": parameters["max_probing_rate"],
            },
            {
                "target_file": parameters["target_file"],
                "probing_rate": parameters["probing_rate"],
                "tool_parameters": parameters["tool_parameters"],
            },
        )

    def dict(self):
        return self._dataclass
