import ipaddress
import upnpclient
import psutil
import socket
from urllib import parse
from socket import gethostbyname

class uPnPClient:
    def __init__(self, interface:str):
        self.interface = interface
        self.port_mapping=[]
        try:
            self.devices = self.get_useful_devices(interface)
            self.available=True
        except:
            print(f"Failed to initialize uPnP client on interface {interface}")
            self.available=False
   
    def get_useful_devices(self,interface):
        devices = upnpclient.discover()
        
        addrs = psutil.net_if_addrs()
        self.available_interfaces = []
        for device, addrs in addrs.items():
            for addr in addrs:
                if addr.family in [socket.AF_INET,socket.AF_INET6]:
                    self.available_interfaces.append(addr.address)

        useful_devices = []
        for device in devices:
            ip=parse.urlparse(device.location).hostname
            try:
                gateip = ipaddress.ip_address(ip)
            except:
                gateip = ipaddress.ip_address(gethostbyname(ip))
            if interface == "0.0.0.0":
                if gateip.version != 4:
                    continue
                devip=None
                net = ipaddress.ip_network(f"{gateip}/24", strict=False)
                for ip in self.available_interfaces:
                    if ipaddress.ip_address(ip) in net:
                        devip = ipaddress.ip_address(ip)
                        break
                if devip is not None:
                    useful_devices.append((device,devip))
            # ipv6 情况
            elif interface == "::":
                if gateip.version != 6:
                    continue
                devip=None
                net = ipaddress.ip_network(f"{gateip}/64", strict=False)
                for ip in self.available_interfaces:
                    if ipaddress.ip_address(ip) in net:
                        devip = ipaddress.ip_address(ip)
                        break
                if devip is not None:
                    useful_devices.append((device,devip))
            else:
                devip = ipaddress.ip_address(interface)
                # 判断两个IP是否在同一个网段之中
                if devip.version == gateip.version:
                    if devip.version == 4:
                        net = ipaddress.ip_network(f"{gateip}/24", strict=False)
                    else:
                        net = ipaddress.ip_network(f"{gateip}/64", strict=False)
                    if devip in net and gateip in net:
                        useful_devices.append((device,devip))
        return useful_devices
    
    def add_port_mapping(self, remote_port:int, local_port:int, protocol:str, description:str):
        if len(self.devices) == 0:
            print(f"No useful devices found on interface {self.interface}")
            return False,[]
        self.port_mapping = []
        for device,devip in self.devices:
            #try:
            remote_ip=device.WANIPConn1.GetExternalIPAddress()['NewExternalIPAddress']
            try:
                device.WANIPConn1.DeletePortMapping(
                    NewRemoteHost='',
                    NewExternalPort=remote_port,
                    NewProtocol=protocol
                )
            except:
                pass
            device.WANIPConn1.AddPortMapping(
                NewRemoteHost='',
                NewExternalPort=remote_port,
                NewProtocol=protocol,
                NewInternalPort=local_port,
                NewInternalClient=devip,
                NewEnabled='1',
                NewPortMappingDescription=description,
                NewLeaseDuration=10000
            )
            self.port_mapping.append((device, remote_port, protocol,remote_ip,devip))
            # except:
            #     pass
        if len(self.port_mapping) == 0:
            print(f"Failed to add port mapping for port {local_port} with protocol {protocol} on interface {devip}")
            return False,[]
        else:
            print(f"Port mapping for port {local_port} with protocol {protocol} on interface {devip} added.")
            return True,[(remote_ip,remote_port,protocol) for _,remote_port,protocol,remote_ip,_ in self.port_mapping]
        
    def remove_port_mapping(self):
        if len(self.port_mapping) == 0:
            print("No port mapping found.")
            return
        for device, port, protocol,_,devip in self.port_mapping:
            try:
                device.WANIPConn1.DeletePortMapping(
                    NewRemoteHost='',
                    NewExternalPort=port,
                    NewProtocol=protocol
                )
                print(f"Port mapping for port {port} with protocol {protocol} on interface {devip} removed.")
            except:
                print(f"Failed to remove port mapping for port {port} with protocol {protocol} on interface {devip}")
        self.port_mapping = []
