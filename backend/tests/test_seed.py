"""种子数据脚本测试。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, enable_sqlite_foreign_keys
from app.models import RegionNetworkPlane
from app.utils.ip_utils import check_overlap, ip_belongs_to_network, parse_cidr, parse_ip
from scripts import seed as seed_module


def test_seed_creates_non_overlapping_sample_planes(monkeypatch):
    """样例网络平面必须符合 CIDR、VLAN 和网关约束。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(seed_module, "engine", engine)
    monkeypatch.setattr(seed_module, "SessionLocal", test_session_local)

    seed_module.seed()

    db = test_session_local()
    try:
        planes = db.query(RegionNetworkPlane).all()
        assert len(planes) == 10

        parsed_planes = []
        vlans_by_region = {}
        for plane in planes:
            assert plane.cidr
            net = parse_cidr(plane.cidr)
            assert net is not None
            assert plane.gateway_ip
            gateway_ip = parse_ip(plane.gateway_ip)
            assert gateway_ip is not None
            assert ip_belongs_to_network(gateway_ip, net)
            if plane.vlan_id is not None:
                region_vlans = vlans_by_region.setdefault(plane.region_id, set())
                assert plane.vlan_id not in region_vlans
                region_vlans.add(plane.vlan_id)
            parsed_planes.append((plane, net))

        for index, (left_plane, left_net) in enumerate(parsed_planes):
            for right_plane, right_net in parsed_planes[index + 1 :]:
                assert not check_overlap(
                    left_net, right_net
                ), f"{left_plane.cidr} should not overlap with {right_plane.cidr}"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
