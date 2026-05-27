"""数据库连接配置与外键约束测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, enable_sqlite_foreign_keys
from app.models.network_plane_type import NetworkPlaneType
from app.models.region import Region
from app.models.region_network_plane import RegionNetworkPlane
from app.models.user import User, UserRegionPermission


def test_enable_sqlite_foreign_keys_turns_on_pragma():
    """SQLite 连接必须启用外键约束。"""
    engine = _create_sqlite_engine()

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_sqlite_foreign_key_cascade_deletes_region_children():
    """绕过 ORM 删除 Region 时，数据库外键级联必须清理子表。"""
    engine = _create_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        region = Region(id="region-1", name="Region-A")
        plane_type = NetworkPlaneType(id="plane-type-1", name="管理平面")
        user = User(id="user-1", username="alice", password_hash="hash", role="user")
        session.add_all([region, plane_type, user])
        session.flush()
        session.add_all(
            [
                RegionNetworkPlane(
                    id="plane-1",
                    region_id=region.id,
                    plane_type_id=plane_type.id,
                    cidr="10.0.0.0/24",
                ),
                UserRegionPermission(id="permission-1", user_id=user.id, region_id=region.id),
            ]
        )
        session.commit()

        with engine.begin() as connection:
            connection.exec_driver_sql("DELETE FROM regions WHERE id = ?", (region.id,))
            remaining_planes = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM region_network_planes WHERE region_id = ?",
                (region.id,),
            ).scalar()
            remaining_permissions = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM user_region_permissions WHERE region_id = ?",
                (region.id,),
            ).scalar()

        assert remaining_planes == 0
        assert remaining_permissions == 0
    finally:
        session.close()
        _drop_all_tables(engine)


def test_sqlite_restricts_deleting_parent_plane_type():
    """绕过业务代码删除父网络平面类型时，数据库外键必须拒绝。"""
    engine = _create_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        parent = NetworkPlaneType(id="parent-type", name="父平面")
        child = NetworkPlaneType(id="child-type", name="子平面", parent_id=parent.id)
        session.add_all([parent, child])
        session.commit()

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql("DELETE FROM network_plane_types WHERE id = ?", (parent.id,))

        assert session.query(NetworkPlaneType).filter_by(id=parent.id).one()
        assert session.query(NetworkPlaneType).filter_by(id=child.id).one()
    finally:
        session.close()
        _drop_all_tables(engine)


def test_sqlite_restricts_deleting_region_used_plane_type():
    """绕过业务代码删除已被 Region 使用的网络平面类型时，数据库外键必须拒绝。"""
    engine = _create_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        region = Region(id="region-1", name="Region-A")
        plane_type = NetworkPlaneType(id="plane-type-1", name="管理平面")
        session.add_all([region, plane_type])
        session.flush()
        session.add(
            RegionNetworkPlane(
                id="plane-1",
                region_id=region.id,
                plane_type_id=plane_type.id,
                cidr="10.0.0.0/24",
            )
        )
        session.commit()

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql("DELETE FROM network_plane_types WHERE id = ?", (plane_type.id,))

        assert session.query(NetworkPlaneType).filter_by(id=plane_type.id).one()
        assert session.query(RegionNetworkPlane).filter_by(id="plane-1").one()
    finally:
        session.close()
        _drop_all_tables(engine)


def test_sqlite_allows_deleting_unused_leaf_plane_type():
    """未被引用且没有子类型的网络平面类型允许在数据库层直接删除。"""
    engine = _create_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        plane_type = NetworkPlaneType(id="plane-type-1", name="可删除平面")
        session.add(plane_type)
        session.commit()

        with engine.begin() as connection:
            connection.exec_driver_sql("DELETE FROM network_plane_types WHERE id = ?", (plane_type.id,))

        assert session.query(NetworkPlaneType).filter_by(id=plane_type.id).first() is None
    finally:
        session.close()
        _drop_all_tables(engine)


def _create_sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    return engine


def _drop_all_tables(engine) -> None:
    with engine.connect() as connection:
        # 测试库销毁阶段关闭外键，避免 RESTRICT 约束阻止 drop 表。
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(bind=connection)
