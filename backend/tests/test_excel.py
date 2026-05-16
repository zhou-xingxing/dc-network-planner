"""Excel 导入导出接口测试。"""

import io

from openpyxl import Workbook, load_workbook


def _workbook_bytes(headers, rows):
    """生成测试导入所需的 xlsx 二进制内容。"""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    buffer.seek(0)
    return buffer.getvalue()


def _setup_import_target(client, admin_headers, user_headers_factory):
    """创建导入确认所需的 Region、PlaneType 和授权用户。"""
    region = client.post("/api/regions", json={"name": "ImportRegion"}, headers=admin_headers).json()
    plane_type = client.post("/api/network-plane-types", json={"name": "导入平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([region["id"]])
    return region, plane_type, user_headers


def test_preview_import_rejects_non_numeric_vlan(client, admin_headers, user_headers_factory):
    """VLAN 非数字时不能静默当成空值导入。"""
    _setup_import_target(client, admin_headers, user_headers_factory)
    file_bytes = _workbook_bytes(
        ["区域名称", "网络平面类型", "作用域", "IP地址段(CIDR)", "VLAN ID", "网关位置", "网关IP"],
        [["ImportRegion", "导入平面", "Global", "10.10.0.0/24", "abc", "CE01", "10.10.0.1"]],
    )

    response = client.post(
        "/api/excel/import/preview",
        files={
            "file": (
                "import.xlsx",
                file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid_rows"] == 0
    assert data["rows"] == []
    assert data["error_rows"][0]["row"] == 2
    assert "无效 VLAN ID: abc" in data["error_rows"][0]["errors"]


def test_preview_import_rows_only_include_valid_rows(client, admin_headers, user_headers_factory):
    """预览响应 rows 只返回确认导入会使用的有效行。"""
    _setup_import_target(client, admin_headers, user_headers_factory)
    file_bytes = _workbook_bytes(
        ["区域名称", "网络平面类型", "作用域", "IP地址段(CIDR)", "VLAN ID", "网关位置", "网关IP"],
        [
            ["ImportRegion", "导入平面", "Global", "10.10.0.0/24", 100, "CE01", "10.10.0.1"],
            ["ImportRegion", "导入平面", "Global", "bad-cidr", 101, "CE02", "10.10.1.1"],
        ],
    )

    response = client.post(
        "/api/excel/import/preview",
        files={
            "file": (
                "import.xlsx",
                file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 2
    assert data["valid_rows"] == 1
    assert [row["row_number"] for row in data["rows"]] == [2]
    assert data["error_rows"][0]["row"] == 3


def test_preview_import_rejects_xls_extension(client, admin_headers):
    """当前解析链路只支持 xlsx，避免把 xls 放行到 500。"""
    response = client.post(
        "/api/excel/import/preview",
        files={"file": ("import.xls", b"not-a-real-xls", "application/vnd.ms-excel")},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "仅支持 .xlsx 文件"


def test_preview_import_rejects_invalid_xlsx(client, admin_headers):
    """损坏的 xlsx 应返回可理解的 400 错误。"""
    response = client.post(
        "/api/excel/import/preview",
        files={
            "file": (
                "import.xlsx",
                b"not-a-workbook",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Excel 文件无法解析，请确认文件为有效的 .xlsx 工作簿"


def test_export_orders_region_planes_by_names(client, admin_headers, user_headers_factory):
    """Excel 导出默认按 Region 名称、网络平面名称、scope 和 CIDR 升序。"""
    region_b = client.post("/api/regions", json={"name": "Region-B"}, headers=admin_headers).json()
    region_a = client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers).json()
    plane_type = client.post("/api/network-plane-types", json={"name": "管理平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    client.post(
        f"/api/regions/{region_b['id']}/planes",
        json={"plane_type_id": plane_type["id"], "cidr": "10.0.2.0/24"},
        headers=user_headers,
    )
    client.post(
        f"/api/regions/{region_a['id']}/planes",
        json={"plane_type_id": plane_type["id"], "cidr": "10.0.1.0/24"},
        headers=user_headers,
    )

    response = client.get("/api/excel/export", headers=admin_headers)

    assert response.status_code == 200
    workbook = load_workbook(io.BytesIO(response.content))
    worksheet = workbook.active
    region_names = [worksheet.cell(row=row_number, column=1).value for row_number in range(2, 4)]
    workbook.close()
    assert region_names == ["Region-A", "Region-B"]
