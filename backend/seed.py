"""
种子数据脚本：为本地开发和演示写入一组符合业务约束的样例数据。
运行方式：python seed.py
"""

import logging
from collections.abc import Mapping

from app.database import Base, SessionLocal, engine
from app.models import NetworkPlaneType, Region, RegionNetworkPlane
from app.utils.ip_utils import IPNetwork, check_overlap, parse_cidr

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PlaneConfig = tuple[str, int, str, str]
RegionPlaneConfigs = Mapping[str, Mapping[str, PlaneConfig]]


def _validate_seed_cidrs(region_plane_configs: RegionPlaneConfigs) -> None:
    """校验样例 CIDR 彼此不重叠，避免种子数据绕过业务层约束。"""
    parsed_networks: list[tuple[str, str, str, IPNetwork]] = []
    for region_name, plane_configs in region_plane_configs.items():
        for plane_name, config in plane_configs.items():
            cidr = config[0]
            net = parse_cidr(cidr)
            if not net:
                raise RuntimeError(f"Invalid seed CIDR: region={region_name}, plane={plane_name}, cidr={cidr}")
            for existing_region, existing_plane, existing_cidr, existing_net in parsed_networks:
                if check_overlap(net, existing_net):
                    raise RuntimeError(
                        "Seed CIDR overlap: "
                        f"{region_name}/{plane_name}/{cidr} overlaps "
                        f"{existing_region}/{existing_plane}/{existing_cidr}"
                    )
            parsed_networks.append((region_name, plane_name, cidr, net))


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 已有 Region 时跳过，避免重复灌入样例数据。
        if db.query(Region).count() > 0:
            logger.info("Database already has data, skipping seed.")
            return

        # 创建网络平面类型。
        plane_types_data = [
            ("管理平面", "用于数据中心管理节点的网络通信", True, "vrf-mgmt"),
            ("业务平面", "用于租户业务流量的网络通信", False, None),
            ("存储平面", "用于存储节点之间的数据同步", True, "vrf-storage"),
            ("内部通信平面", "用于数据中心内部组件之间的通信", True, "vrf-internal"),
            ("BMC平面", "用于服务器BMC管理口网络", True, "vrf-bmc"),
        ]

        plane_types = {}
        for name, desc, is_private, vrf in plane_types_data:
            pt = NetworkPlaneType(name=name, description=desc, is_private=is_private, vrf=vrf)
            db.add(pt)
            db.flush()
            plane_types[name] = pt
            logger.info("  Created plane type: %s", name)

        # 创建 Region。
        regions_data = [
            ("北京数据中心", "华北区域生产环境"),
            ("上海数据中心", "华东区域生产环境"),
        ]

        # 样例地址按 Region 分配独立网段，符合跨 Region CIDR 不重叠约束。
        region_plane_configs = {
            "北京数据中心": {
                "管理平面": ("10.10.0.0/16", 100, "MGMT-BJ-SW01 / MGMT-BJ-SW02", "10.10.0.1"),
                "业务平面": (
                    "172.16.0.0/16",
                    200,
                    "SERVICE-BJ-SW01 / SERVICE-BJ-SW02",
                    "172.16.255.254",
                ),
                "存储平面": (
                    "192.168.10.0/24",
                    300,
                    "STORAGE-BJ-SW01 / STORAGE-BJ-SW02",
                    "192.168.10.1",
                ),
                "内部通信平面": (
                    "10.20.0.0/16",
                    400,
                    "INNER-BJ-SW01 / INNER-BJ-SW02",
                    "10.20.0.1",
                ),
                "BMC平面": (
                    "192.168.100.0/24",
                    500,
                    "BMC-BJ-SW01 / BMC-BJ-SW02",
                    "192.168.100.1",
                ),
            },
            "上海数据中心": {
                "管理平面": ("10.11.0.0/16", 100, "MGMT-SH-SW01 / MGMT-SH-SW02", "10.11.0.1"),
                "业务平面": (
                    "172.17.0.0/16",
                    200,
                    "SERVICE-SH-SW01 / SERVICE-SH-SW02",
                    "172.17.255.254",
                ),
                "存储平面": (
                    "192.168.11.0/24",
                    300,
                    "STORAGE-SH-SW01 / STORAGE-SH-SW02",
                    "192.168.11.1",
                ),
                "内部通信平面": (
                    "10.21.0.0/16",
                    400,
                    "INNER-SH-SW01 / INNER-SH-SW02",
                    "10.21.0.1",
                ),
                "BMC平面": (
                    "192.168.101.0/24",
                    500,
                    "BMC-SH-SW01 / BMC-SH-SW02",
                    "192.168.101.1",
                ),
            },
        }
        _validate_seed_cidrs(region_plane_configs)

        created_regions = {}
        for name, desc in regions_data:
            region = Region(name=name, description=desc)
            db.add(region)
            db.flush()
            created_regions[name] = region
            logger.info("  Created region: %s", name)

            # 为每个 Region 启用全部平面类型，并写入 CIDR、VLAN 和网关信息。
            plane_configs = region_plane_configs[name]
            for pt_name, pt in plane_types.items():
                cidr, vlan_id, gateway_position, gateway_ip = plane_configs[pt_name]
                rp = RegionNetworkPlane(
                    region_id=region.id,
                    plane_type_id=pt.id,
                    cidr=cidr,
                    vlan_id=vlan_id,
                    gateway_position=gateway_position,
                    gateway_ip=gateway_ip,
                )
                db.add(rp)

        db.commit()
        logger.info("\nSeed completed successfully!")
        logger.info("  Regions: %d", len(created_regions))
        logger.info("  Plane Types: %d", len(plane_types))
        logger.info("  Region Network Planes: %d", len(created_regions) * len(plane_types))

    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Seeding database...")
    seed()
