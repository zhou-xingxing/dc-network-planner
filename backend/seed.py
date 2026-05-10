"""
Seed script: populate the database with sample data for development/testing.
Run with: python seed.py
"""

import logging

from app.database import Base, SessionLocal, engine
from app.models import NetworkPlaneType, Region, RegionNetworkPlane

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(Region).count() > 0:
            logger.info("Database already has data, skipping seed.")
            return

        # Create network plane types
        plane_types_data = [
            ("管理平面", "用于数据中心管理节点的网络通信", True, "vrf-mgmt"),
            ("业务平面", "用于租户业务流量的网络通信", False, None),
            ("存储平面", "用于存储节点之间的数据同步", True, "vrf-storage"),
            ("内部通信平面", "用于数据中心内部组件之间的通信", True, "vrf-internal"),
            ("BMC平面", "用于服务器BMC管理口网络", True, "vrf-bmc"),
        ]

        plane_types = {}
        for name, desc, is_private, vrf in plane_types_data:
            pt = NetworkPlaneType(
                name=name, description=desc, is_private=is_private, vrf=vrf
            )
            db.add(pt)
            db.flush()
            plane_types[name] = pt
            logger.info("  Created plane type: %s", name)

        # Create regions
        regions_data = [
            ("北京数据中心", "华北区域生产环境"),
            ("上海数据中心", "华东区域生产环境"),
        ]

        created_regions = {}
        for name, desc in regions_data:
            region = Region(name=name, description=desc)
            db.add(region)
            db.flush()
            created_regions[name] = region
            logger.info("  Created region: %s", name)

            # Enable all plane types for each region (with CIDR and gateway metadata)
            plane_configs = {
                "管理平面": ("10.10.0.0/16", 100, "MGMT-SW01 / MGMT-SW02", "10.10.0.1"),
                "业务平面": (
                    "172.16.0.0/16",
                    200,
                    "SERVICE-SW01 / SERVICE-SW02",
                    "172.16.255.254",
                ),
                "存储平面": (
                    "192.168.10.0/24",
                    300,
                    "STORAGE-SW01 / STORAGE-SW02",
                    "192.168.10.1",
                ),
                "内部通信平面": (
                    "10.20.0.0/16",
                    400,
                    "INNER-SW01 / INNER-SW02",
                    "10.20.0.1",
                ),
                "BMC平面": (
                    "192.168.100.0/24",
                    500,
                    "BMC-SW01 / BMC-SW02",
                    "192.168.100.1",
                ),
            }
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
        logger.info(
            "  Region Network Planes: %d", len(created_regions) * len(plane_types)
        )

    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Seeding database...")
    seed()
