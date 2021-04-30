"""Prober executor."""

import asyncio

from diamond_miner.generator import probe_generator_by_flow
from pycaracal import cast_addr, make_probe, prober, set_log_level


async def watcher(
    process, settings, measurement_uuid, logger, logger_prefix="", redis=None
) -> bool:
    """Watch the prober execution and stop it according to the measurement state."""
    while process.is_alive():
        if redis is not None:
            measurement_state = await redis.get_measurement_state(measurement_uuid)
            if measurement_state is None:
                process.kill()
                logger.warning(logger_prefix + "Measurement canceled")
                return False
        await asyncio.sleep(settings.WORKER_STOPPER_REFRESH)
    return True


def probe(
    settings,
    results_filepath,
    round_number,
    probing_rate,
    gen_parameters=None,
    probes_filepath=None,
):
    """Probing interface."""

    # Cap the probing rate if superior to the maximum probing rate
    measurement_probing_rate = (
        probing_rate
        if probing_rate and probing_rate <= settings.AGENT_MAX_PROBING_RATE
        else settings.AGENT_MAX_PROBING_RATE
    )

    # This set the log level of the C++ logger (spdlog).
    # This allow the logs to be filtered in C++ (fast)
    # before being forwarded to the (slower) Python logger.
    set_log_level(settings.AGENT_PROBER_LOGGING_LEVEL)

    # Prober configuration
    config = prober.Config()
    config.set_output_file_csv(results_filepath)

    config.set_probing_rate(measurement_probing_rate)
    config.set_rate_limiting_method(settings.AGENT_PROBER_RATE_LIMITING_METHOD.value)
    config.set_meta_round(str(round_number))

    if settings.AGENT_PROBER_EXCLUDE_PATH is None:
        config.filter_from_prefix_file_excl(settings.AGENT_PROBER_EXCLUDE_PATH)

    if round_number == 1:
        # Map generator tuples to pycaracal Probes
        # * protocol is "icmp", "icmp6", or "udp",
        #   this is different from before where we only had "icmp" or "udp"!
        # * cast_addr converts an IPv4/IPv6 object, or an IPv6 as an integer
        #   to an in6_addr struct in C.
        gen = probe_generator_by_flow(**gen_parameters)
        gen = (
            make_probe(
                cast_addr(dst_addr),
                src_port,
                dst_port,
                ttl,
                protocol,
            )
            for dst_addr, src_port, dst_port, ttl, protocol in gen
        )

        # Use the prober generator
        prober.probe(config, gen)
    else:
        # In case of round > 1, use a probes file
        prober.probe(config, probes_filepath)
