import socket
from ipaddress import IPv4Address, IPv6Address

from iris.commons.utils import get_ipv4_address, get_ipv6_address

# IPv4


def test_get_ipv4_address(monkeypatch):
    """Test get own ipv4 address."""

    class Socket(object):
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

        def getsockname(self, *args, **kwargs):
            return ("1.2.3.4",)

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", Socket)
    assert get_ipv4_address() == IPv4Address("1.2.3.4")


def test_get_ipv4_address_error(monkeypatch):
    """Test get own ipv4 address when it's not possible."""

    class Socket(object):
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

        def getsockname(self, *args, **kwargs):
            raise Exception

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", Socket)
    assert get_ipv4_address() == IPv4Address("127.0.0.1")


# IPv6


def test_get_ipv6_address(monkeypatch):
    """Test get own ipv6 address."""

    class Socket(object):
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

        def getsockname(self, *args, **kwargs):
            return ("::1234",)

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", Socket)
    assert get_ipv6_address() == IPv6Address("::1234")


def test_get_ipv6_address_error(monkeypatch):
    """Test get own ipv6 address when it's not possible."""

    class Socket(object):
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

        def getsockname(self, *args, **kwargs):
            raise Exception

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", Socket)
    assert get_ipv6_address() == IPv6Address("::1")
