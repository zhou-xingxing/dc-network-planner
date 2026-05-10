"""Excel 导出接口测试。"""

import io

from openpyxl import load_workbook


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
