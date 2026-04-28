"""UPnP 客户端：自动发现网关并管理端口映射。

UPnP client: auto-discovers gateway devices and manages port mappings.
"""
from __future__ import annotations

import concurrent.futures
import ipaddress
import logging
import socket
from socket import gethostbyname
from typing import Optional
from urllib import parse

# 标记 upnpclient 库是否已安装。
# Flag indicating whether the upnpclient library is installed.
requirements_installed = True
try:
    import upnpclient
except ImportError:
    requirements_installed = False

logger = logging.getLogger(__name__)


def _get_local_addresses() -> list[str]:
    """获取本机所有 IPv4/IPv6 地址（不依赖 psutil）。

    Return all local IPv4/IPv6 addresses without relying on psutil.
    """
    addrs: list[str] = []
    for fam in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(None, 0, fam, socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        for info in infos:
            ip = str(info[4][0])
            if ip not in addrs:
                addrs.append(ip)
    return addrs


def _discover_with_timeout(timeout: float = 10.0) -> list:
    """带超时的 UPnP 设备发现，避免无限阻塞。

    Discover UPnP devices with a timeout to prevent infinite blocking.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(upnpclient.discover)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("uPnP device discovery timed out after %.0fs", timeout)
            return []


class UPnPClient:
    """UPnP 客户端，支持端口映射的添加与移除。

    UPnP client that supports adding and removing port mappings.
    """

    def __init__(self, interface: str, discover_timeout: float = 10.0) -> None:
        """初始化 UPnP 客户端并发现可用网关设备。

        Initialise the UPnP client and discover available gateway devices.

        Args:
            interface: 本地网络接口地址。 / Local network interface address.
            discover_timeout: 设备发现超时（秒）。 / Device discovery timeout in seconds.
        """
        self.available: bool
        self.interface: str
        self.port_mapping: list[tuple]
        self.devices: list
        self.available_interfaces: list[str]

        if not requirements_installed:
            self.available = False
            logger.warning(
                "uPnP client is not available because upnpclient is not installed. "
                "Please install it using 'pip install upnpclient' "
                "or 'pip install cryskura[upnp]'"
            )
            return

        self.available = True
        self.interface = interface
        self.port_mapping = []
        self._discover_timeout: float = discover_timeout
        try:
            self.devices = self.get_useful_devices(interface)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to initialize uPnP client on interface %s", interface
            )
            self.available = False

    def get_useful_devices(self, interface: str) -> list[tuple]:
        """发现并筛选与指定接口同子网的网关设备。

        Discover and filter gateway devices that share the subnet of the given interface.

        Args:
            interface: 本地网络接口地址。 / Local network interface address.

        Returns:
            list[tuple]: (device, devip) 元组列表。 / List of (device, devip) tuples.
        """
        if not self.available:
            raise ValueError("uPnP client is not available.")

        devices = _discover_with_timeout(self._discover_timeout)
        self.available_interfaces = _get_local_addresses()

        useful_devices: list[tuple] = []
        for device in devices:
            ip = parse.urlparse(device.location).hostname
            try:
                gateip = ipaddress.ip_address(ip)
            except ValueError:
                gateip = ipaddress.ip_address(gethostbyname(ip))

            devip: Optional[ipaddress.IPv4Address | ipaddress.IPv6Address] = None
            if interface == "0.0.0.0":
                if gateip.version != 4:
                    continue
                net = ipaddress.ip_network(f"{gateip}/24", strict=False)
                for iface_ip in self.available_interfaces:
                    if ipaddress.ip_address(iface_ip) in net:
                        devip = ipaddress.ip_address(iface_ip)
                        break
            elif interface == "::1":
                if gateip.version != 6:
                    continue
                net = ipaddress.ip_network(f"{gateip}/64", strict=False)
                for iface_ip in self.available_interfaces:
                    if ipaddress.ip_address(iface_ip) in net:
                        devip = ipaddress.ip_address(iface_ip)
                        break
            else:
                devip = ipaddress.ip_address(interface)
                if devip.version == gateip.version:
                    if devip.version == 4:
                        net = ipaddress.ip_network(f"{gateip}/24", strict=False)
                    else:
                        net = ipaddress.ip_network(f"{gateip}/64", strict=False)
                    if devip not in net or gateip not in net:
                        devip = None

            if devip is not None:
                useful_devices.append((device, devip))

        return useful_devices

    def add_port_mapping(
        self,
        remote_port: int,
        local_port: int,
        protocol: str,
        description: str,
    ) -> tuple[bool, list[tuple]]:
        """在网关上添加端口映射。

        Add a port mapping on the gateway device.

        Args:
            remote_port: 外部（WAN）端口。 / External (WAN) port.
            local_port: 内部（LAN）端口。 / Internal (LAN) port.
            protocol: 协议（"TCP" 或 "UDP"）。 / Protocol ("TCP" or "UDP").
            description: 映射描述。 / Mapping description.

        Returns:
            tuple[bool, list[tuple]]: 成功标志和映射信息列表。
                                      Success flag and list of mapping info.
        """
        if not self.available:
            raise ValueError("uPnP client is not available.")

        if len(self.devices) == 0:
            logger.info("No useful devices found on interface %s", self.interface)
            return False, []

        self.port_mapping = []
        for device, devip in self.devices:
            remote_ip = device.WANIPConn1.GetExternalIPAddress()[
                'NewExternalIPAddress'
            ]
            try:
                device.WANIPConn1.DeletePortMapping(
                    NewRemoteHost='0.0.0.0',
                    NewExternalPort=remote_port,
                    NewProtocol=protocol,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            device.WANIPConn1.AddPortMapping(
                NewRemoteHost='0.0.0.0',
                NewExternalPort=remote_port,
                NewProtocol=protocol,
                NewInternalPort=local_port,
                NewInternalClient=devip,
                NewEnabled='1',
                NewPortMappingDescription=description,
                NewLeaseDuration=10000,
            )
            self.port_mapping.append(
                (device, remote_port, protocol, remote_ip, devip)
            )

        if len(self.port_mapping) == 0:
            logger.error(
                "Failed to add port mapping for port %d with protocol %s",
                local_port, protocol,
            )
            return False, []
        logger.info(
            "Port mapping for port %d with protocol %s added.",
            local_port, protocol,
        )
        return True, [
            (remote_ip, remote_port, protocol)
            for _, remote_port, protocol, remote_ip, _ in self.port_mapping
        ]

    def remove_port_mapping(self) -> None:
        """移除所有已添加的端口映射。

        Remove all previously added port mappings.
        """
        if not self.available:
            raise ValueError("uPnP client is not available.")

        if len(self.port_mapping) == 0:
            logger.info("No port mapping found.")
            return

        for device, port, protocol, _remote_ip, devip in self.port_mapping:
            try:
                device.WANIPConn1.DeletePortMapping(
                    NewRemoteHost='0.0.0.0',
                    NewExternalPort=port,
                    NewProtocol=protocol,
                )
                logger.info(
                    "Port mapping for port %d with protocol %s "
                    "on interface %s removed.",
                    port, protocol, devip,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Failed to remove port mapping for port %d "
                    "with protocol %s on interface %s",
                    port, protocol, devip,
                )

        self.port_mapping = []


# 向后兼容别名 / Backward-compatible alias.
uPnPClient = UPnPClient
