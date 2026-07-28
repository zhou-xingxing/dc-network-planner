"""交换机布线管理数据模型约束测试。"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cabling import CableEntry, CablingBatch
from app.models.rack import Rack
from app.models.region import Region
from app.models.switch import Switch, SwitchBusinessType, SwitchGroup, SwitchPort


def test_cabling_models_store_batch_and_endpoint_relationships(test_db) -> None:
    """布线批次应通过线缆条目关联服务器端口和交换机端口。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        batch = CablingBatch(
            id="batch-1",
            region_id=topology.region.id,
            name="第一批布线",
            created_by="alice",
        )
        entry = CableEntry(
            id="entry-1",
            batch=batch,
            server_rack=topology.server_rack,
            server_start_u=10,
            server_height_u=2,
            server_port_name="NIC1",
            switch_port=topology.switch_port,
            cable_label="CBL-000001",
            cable_sequence=1,
            comment="首条线缆",
        )
        session.add(entry)
        session.commit()

        stored_entry = session.query(CableEntry).filter_by(id=entry.id).one()
        assert stored_entry.batch.name == "第一批布线"
        assert stored_entry.server_rack.name == "A01"
        assert stored_entry.server_start_u == 10
        assert stored_entry.server_height_u == 2
        assert stored_entry.server_port_name == "NIC1"
        assert stored_entry.cable_sequence == 1
        assert stored_entry.comment == "首条线缆"
        assert stored_entry.switch_port.switch.name == "switch-a"
        assert stored_entry.switch_port.switch.switch_group is not None
        assert stored_entry.switch_port.switch.switch_group.business_type.code == "business"
        assert stored_entry.switch_port.switch.switch_group.business_type.name == "业务"
        assert stored_entry.switch_port.switch.rack.name == "N01"
        assert stored_entry.switch_port.switch.port_speed_mbps == 25000
    finally:
        session.close()


def test_switch_name_is_globally_unique(test_db) -> None:
    """交换机名称在不同 Region 间也不能重复。"""
    session = Session(test_db)
    try:
        _create_topology(session)
        session.commit()

        second_region = Region(id="region-2", name="Region-B")
        second_rack = Rack(id="rack-switch-2", region_id=second_region.id, name="N02")
        session.add_all([second_region, second_rack])
        session.flush()
        session.add(
            Switch(
                id="switch-2",
                rack_id=second_rack.id,
                name="switch-a",
                port_speed_mbps=10000,
                start_u=1,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_switch_group_member_role_is_unique(test_db) -> None:
    """同一交换机组中不能重复配置相同成员角色。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        duplicate_role_switch = Switch(
            id="switch-a-duplicate",
            rack_id=topology.switch_rack.id,
            switch_group_id=topology.switch_group.id,
            member_role="a",
            name="switch-a-duplicate",
            port_speed_mbps=25000,
            start_u=41,
        )
        session.add(duplicate_role_switch)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_switch_port_speed_mbps_must_be_positive(test_db) -> None:
    """交换机端口速率必须是正整数 Mbps。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        session.add(
            Switch(
                id="switch-invalid-speed",
                rack_id=topology.switch_rack.id,
                name="switch-invalid-speed",
                port_speed_mbps=0,
                start_u=41,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_switch_port_number_is_unique_within_switch(test_db) -> None:
    """同一交换机内不能重复配置端口编号。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        session.add(
            SwitchPort(
                id="switch-port-duplicate",
                switch_id=topology.switch.id,
                port_number=1,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


@pytest.mark.parametrize(
    ("code", "name"),
    [("business", "其他"), ("other", "业务")],
    ids=["code", "name"],
)
def test_switch_business_type_code_and_name_are_globally_unique(test_db, code: str, name: str) -> None:
    """交换机业务类型的英文标识和中文名称都必须全局唯一。"""
    session = Session(test_db)
    try:
        _create_topology(session)
        session.add(SwitchBusinessType(id="business-type-2", code=code, name=name))

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_cable_entry_prevents_reusing_server_port(test_db) -> None:
    """线缆条目占用服务器端口，删除后允许新批次重新使用。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        second_switch_port = SwitchPort(
            id="switch-port-2",
            switch_id=topology.switch.id,
            port_number=2,
        )
        first_batch = CablingBatch(id="batch-1", region_id=topology.region.id, name="第一批布线", created_by="alice")
        second_batch = CablingBatch(id="batch-2", region_id=topology.region.id, name="第二批布线", created_by="alice")
        first_entry = CableEntry(
            id="entry-1",
            batch=first_batch,
            server_rack=topology.server_rack,
            server_start_u=10,
            server_height_u=2,
            server_port_name="NIC1",
            switch_port=topology.switch_port,
            cable_label="CBL-000001",
            cable_sequence=1,
        )
        session.add_all([second_switch_port, second_batch, first_entry])
        session.commit()

        session.add(
            CableEntry(
                id="entry-conflict",
                batch_id=second_batch.id,
                server_rack_id=topology.server_rack.id,
                server_start_u=10,
                server_height_u=3,
                server_port_name="NIC1",
                switch_port_id=second_switch_port.id,
                cable_label="CBL-000002",
                cable_sequence=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        stored_first_entry = session.get(CableEntry, first_entry.id)
        assert stored_first_entry is not None
        session.delete(stored_first_entry)
        session.commit()

        session.add(
            CableEntry(
                id="entry-2",
                batch_id=second_batch.id,
                server_rack_id=topology.server_rack.id,
                server_start_u=10,
                server_height_u=2,
                server_port_name="NIC1",
                switch_port_id=second_switch_port.id,
                cable_label="CBL-000002",
                cable_sequence=1,
            )
        )
        session.commit()

        assert session.get(CableEntry, "entry-2") is not None
    finally:
        session.close()


def test_cable_entry_prevents_reusing_switch_port(test_db) -> None:
    """线缆条目占用交换机端口，不能同时分配给另一服务器端口。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        first_batch = CablingBatch(id="batch-1", region_id=topology.region.id, name="第一批布线", created_by="alice")
        second_batch = CablingBatch(id="batch-2", region_id=topology.region.id, name="第二批布线", created_by="alice")
        session.add_all(
            [
                first_batch,
                second_batch,
                CableEntry(
                    id="entry-1",
                    batch=first_batch,
                    server_rack=topology.server_rack,
                    server_start_u=10,
                    server_height_u=2,
                    server_port_name="NIC1",
                    switch_port=topology.switch_port,
                    cable_label="CBL-000001",
                    cable_sequence=1,
                ),
            ]
        )
        session.commit()

        session.add(
            CableEntry(
                id="entry-conflict",
                batch_id=second_batch.id,
                server_rack_id=topology.server_rack.id,
                server_start_u=10,
                server_height_u=2,
                server_port_name="NIC2",
                switch_port_id=topology.switch_port.id,
                cable_label="CBL-000002",
                cable_sequence=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_cable_label_can_be_reused_after_deleting_entry(test_db) -> None:
    """线签不能重复使用，删除原线缆条目后才允许复用。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        second_switch_port = SwitchPort(
            id="switch-port-2",
            switch_id=topology.switch.id,
            port_number=2,
        )
        first_batch = CablingBatch(id="batch-1", region_id=topology.region.id, name="第一批布线", created_by="alice")
        second_batch = CablingBatch(id="batch-2", region_id=topology.region.id, name="第二批布线", created_by="alice")
        session.add_all(
            [
                second_switch_port,
                first_batch,
                second_batch,
                CableEntry(
                    id="entry-1",
                    batch=first_batch,
                    server_rack=topology.server_rack,
                    server_start_u=10,
                    server_height_u=2,
                    server_port_name="NIC1",
                    switch_port=topology.switch_port,
                    cable_label="CBL-000001",
                    cable_sequence=1,
                ),
            ]
        )
        session.commit()

        second_entry = CableEntry(
            id="entry-2",
            batch_id=second_batch.id,
            server_rack_id=topology.server_rack.id,
            server_start_u=10,
            server_height_u=2,
            server_port_name="NIC2",
            switch_port_id=second_switch_port.id,
            cable_label="CBL-000001",
            cable_sequence=1,
        )
        session.add(second_entry)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        first_entry = session.get(CableEntry, "entry-1")
        assert first_entry is not None
        session.delete(first_entry)
        session.commit()

        session.add(second_entry)
        session.commit()

        assert session.get(CableEntry, "entry-2") is not None
        assert session.get(CableEntry, "entry-1") is None
    finally:
        session.close()


def test_cable_entry_restricts_deleting_referenced_resources(test_db) -> None:
    """已有线缆条目时数据库必须拒绝删除批次、服务器侧机柜或交换机端口。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        batch = CablingBatch(id="batch-1", region_id=topology.region.id, name="第一批布线", created_by="alice")
        entry = CableEntry(
            id="entry-1",
            batch=batch,
            server_rack=topology.server_rack,
            server_start_u=10,
            server_height_u=2,
            server_port_name="NIC1",
            switch_port=topology.switch_port,
            cable_label="CBL-000001",
            cable_sequence=1,
        )
        session.add(entry)
        session.commit()

        for table_name, row_id in (
            ("cabling_batches", batch.id),
            ("racks", topology.server_rack.id),
            ("switch_ports", topology.switch_port.id),
        ):
            with pytest.raises(IntegrityError):
                with test_db.begin() as connection:
                    connection.exec_driver_sql(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
    finally:
        session.close()


def test_region_with_cabling_resources_cannot_be_deleted_directly(test_db) -> None:
    """Region 下存在布线资源时数据库外键必须阻止直接删除 Region。"""
    session = Session(test_db)
    try:
        topology = _create_topology(session)
        session.commit()

        with pytest.raises(IntegrityError):
            with test_db.begin() as connection:
                connection.exec_driver_sql("DELETE FROM regions WHERE id = ?", (topology.region.id,))
    finally:
        session.close()


def test_switch_business_type_in_use_cannot_be_deleted_directly(test_db) -> None:
    """交换机组正在使用的业务类型不能直接删除。"""
    session = Session(test_db)
    try:
        _create_topology(session)
        session.commit()

        with pytest.raises(IntegrityError):
            with test_db.begin() as connection:
                connection.exec_driver_sql(
                    "DELETE FROM switch_business_types WHERE id = ?",
                    ("business-type-1",),
                )
    finally:
        session.close()


class _Topology:
    """模型约束测试使用的最小布线资源集合。"""

    def __init__(
        self,
        *,
        region: Region,
        server_rack: Rack,
        switch_rack: Rack,
        switch_group: SwitchGroup,
        switch: Switch,
        switch_port: SwitchPort,
    ) -> None:
        self.region = region
        self.server_rack = server_rack
        self.switch_rack = switch_rack
        self.switch_group = switch_group
        self.switch = switch
        self.switch_port = switch_port


def _create_topology(session: Session) -> _Topology:
    """创建服务器侧机柜、业务交换机及交换机端口。"""
    region = Region(id="region-1", name="Region-A")
    server_rack = Rack(id="rack-server", region_id=region.id, name="A01")
    switch_rack = Rack(id="rack-switch", region_id=region.id, name="N01")
    business_type = SwitchBusinessType(id="business-type-1", code="business", name="业务")
    switch_group = SwitchGroup(
        id="switch-group-1",
        region_id=region.id,
        name="业务交换机对-01",
        business_type=business_type,
        group_mode="pair",
    )
    session.add_all([region, server_rack, switch_rack, business_type, switch_group])
    session.flush()

    switch = Switch(
        id="switch-1",
        rack_id=switch_rack.id,
        switch_group_id=switch_group.id,
        member_role="a",
        name="switch-a",
        port_speed_mbps=25000,
        start_u=42,
    )
    session.add(switch)
    session.flush()

    switch_port = SwitchPort(
        id="switch-port-1",
        switch_id=switch.id,
        port_number=1,
    )
    session.add(switch_port)
    session.flush()

    return _Topology(
        region=region,
        server_rack=server_rack,
        switch_rack=switch_rack,
        switch_group=switch_group,
        switch=switch,
        switch_port=switch_port,
    )
