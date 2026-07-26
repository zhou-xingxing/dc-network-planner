from __future__ import annotations

import ipaddress
from typing import Optional, Union

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def parse_cidr(cidr_str: str) -> Optional[IPNetwork]:
    """Parse a CIDR string into an IP network object.

    Args:
        cidr_str: CIDR 字符串，如 "10.0.0.0/24"。

    Returns:
        解析后的 IPv4Network 或 IPv6Network 对象。
        格式非法时返回 None。
    """
    try:
        return ipaddress.IPv4Network(cidr_str, strict=False)
    except (ValueError, TypeError):
        pass
    try:
        return ipaddress.IPv6Network(cidr_str, strict=False)
    except (ValueError, TypeError):
        pass
    return None


def parse_ip(ip_str: str) -> Optional[IPAddress]:
    """Parse an IP address string.

    Args:
        ip_str: IP 地址字符串，如 "10.0.0.5"。

    Returns:
        解析后的 IPv4Address 或 IPv6Address 对象。
        格式非法时返回 None。
    """
    try:
        return ipaddress.IPv4Address(ip_str)
    except (ValueError, TypeError):
        pass
    try:
        return ipaddress.IPv6Address(ip_str)
    except (ValueError, TypeError):
        pass
    return None


def cidr_uses_host_address(cidr_str: str, net: IPNetwork | None = None) -> bool:
    """判断 CIDR 地址部分是否使用了网段内的主机地址。

    CIDR 地址部分应使用网段的网络地址，而不是网段内的主机地址。
    例如，``10.0.0.1/24`` 使用了 ``10.0.0.0/24`` 网段内的主机地址，
    应改为 ``10.0.0.0/24``；``2001:db8::1/64`` 同理，应改为
    ``2001:db8::/64``。

    Args:
        cidr_str: CIDR 字符串，如 ``10.0.0.1/30``。
        net: 从同一 CIDR 解析出的网络对象；传入时复用，避免重复解析。

    Returns:
        True 表示 CIDR 地址部分使用了网段内的主机地址。

        False 有两种含义：斜杠前的地址就是网络地址，例如
        ``10.0.0.0/24``；或者输入无法完成判断，例如 CIDR 格式无效、
        缺少斜杠、地址与 ``net`` 的 IP 版本不一致。因此，返回 False
        不代表 CIDR 格式有效，调用方仍需单独完成格式校验。
    """
    parsed_net = net or parse_cidr(cidr_str)
    if not parsed_net:
        return False
    address_text, separator, _ = cidr_str.partition("/")
    if not separator:
        return False
    address = parse_ip(address_text)
    return address is not None and address.version == parsed_net.version and address != parsed_net.network_address


def check_overlap(net1: IPNetwork, net2: IPNetwork) -> bool:
    """Check if two CIDR networks overlap.

    Args:
        net1: 第一个网络对象。
        net2: 第二个网络对象。

    Returns:
        两个网络有重叠则返回 True。
    """
    if isinstance(net1, ipaddress.IPv4Network) and isinstance(net2, ipaddress.IPv4Network):
        return net1.overlaps(net2)
    if isinstance(net1, ipaddress.IPv6Network) and isinstance(net2, ipaddress.IPv6Network):
        return net1.overlaps(net2)
    return False


def ip_belongs_to_network(ip: IPAddress, net: IPNetwork) -> bool:
    """Check if an IP object belongs to a same-version network object.

    Args:
        ip: IP 地址对象。
        net: CIDR 网络对象。

    Returns:
        IP 与 CIDR 同版本且 IP 位于 CIDR 范围内则返回 True。
    """
    if isinstance(ip, ipaddress.IPv4Address) and isinstance(net, ipaddress.IPv4Network):
        return ip in net
    if isinstance(ip, ipaddress.IPv6Address) and isinstance(net, ipaddress.IPv6Network):
        return ip in net
    return False


def network_is_subnet_of(child: IPNetwork, parent: IPNetwork) -> bool:
    """Check if a CIDR network is a subnet of another same-version network.

    Args:
        child: 子网络对象。
        parent: 父网络对象。

    Returns:
        child 与 parent 同版本且 child 属于 parent 范围内则返回 True。
    """
    if isinstance(child, ipaddress.IPv4Network) and isinstance(parent, ipaddress.IPv4Network):
        return child.subnet_of(parent)
    if isinstance(child, ipaddress.IPv6Network) and isinstance(parent, ipaddress.IPv6Network):
        return child.subnet_of(parent)
    return False


def find_first_available_subnet(
    parent: IPNetwork,
    prefix_length: int,
    occupied_networks: list[IPNetwork],
) -> IPNetwork | None:
    """在父网段内查找地址最低的首个可用子网。

    已占用网段先转换成目标子网序号区间，再合并区间寻找空洞，避免
    枚举 IPv6 父网段可能包含的海量候选子网。

    Args:
        parent: 用于分配子网的父网段。
        prefix_length: 目标子网的掩码位数。
        occupied_networks: 不能与候选子网重叠的已有网段。

    Returns:
        地址最低的首个可用子网；父网段空间耗尽时返回 None。

    Raises:
        ValueError: 目标掩码无法在父网段内形成子网。
    """
    if prefix_length < parent.prefixlen or prefix_length > parent.max_prefixlen:
        raise ValueError("目标掩码必须位于父网段掩码与地址族最大掩码之间")

    parent_start = int(parent.network_address)
    parent_end = int(parent.broadcast_address)
    block_size = 1 << (parent.max_prefixlen - prefix_length)
    candidate_count = parent.num_addresses // block_size
    blocked_ranges: list[tuple[int, int]] = []

    for occupied in occupied_networks:
        if occupied.version != parent.version or not occupied.overlaps(parent):
            continue
        occupied_start = max(parent_start, int(occupied.network_address))
        occupied_end = min(parent_end, int(occupied.broadcast_address))
        blocked_ranges.append(
            (
                (occupied_start - parent_start) // block_size,
                (occupied_end - parent_start) // block_size,
            )
        )

    candidate_index = 0
    for blocked_start, blocked_end in sorted(blocked_ranges):
        if blocked_end < candidate_index:
            continue
        if blocked_start > candidate_index:
            break
        candidate_index = blocked_end + 1
        if candidate_index >= candidate_count:
            return None

    candidate_start = parent_start + candidate_index * block_size
    if isinstance(parent, ipaddress.IPv4Network):
        return ipaddress.IPv4Network((candidate_start, prefix_length))
    return ipaddress.IPv6Network((candidate_start, prefix_length))


def find_overlapping(cidr_str: str, existing_cidrs: list[str]) -> list[str]:
    """Find which existing CIDRs overlap with the given CIDR.

    Args:
        cidr_str: 待检查的 CIDR 字符串。
        existing_cidrs: 已有 CIDR 列表。

    Returns:
        与 cidr_str 重叠的已有 CIDR 字符串列表。
    """
    target = parse_cidr(cidr_str)
    if not target:
        return []
    overlapping = []
    for ec in existing_cidrs:
        existing = parse_cidr(ec)
        if existing and check_overlap(target, existing):
            overlapping.append(ec)
    return overlapping


def ip_in_network(ip_str: str, cidr_str: str) -> bool:
    """Check if an IP address belongs to a CIDR network.

    Args:
        ip_str: IP 地址字符串。
        cidr_str: CIDR 字符串。

    Returns:
        IP 在网络的 CIDR 范围内则返回 True。
    """
    ip = parse_ip(ip_str)
    net = parse_cidr(cidr_str)
    if ip and net:
        return ip_belongs_to_network(ip, net)
    return False


def find_containing_networks(ip_str: str, existing_cidrs: list[str]) -> list[str]:
    """Find which existing CIDRs contain the given IP.

    Args:
        ip_str: IP 地址字符串。
        existing_cidrs: 已有 CIDR 列表。

    Returns:
        包含该 IP 的已有 CIDR 字符串列表。
    """
    ip = parse_ip(ip_str)
    if not ip:
        return []
    containing = []
    for ec in existing_cidrs:
        net = parse_cidr(ec)
        if net and ip_belongs_to_network(ip, net):
            containing.append(ec)
    return containing
