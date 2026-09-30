# 창고 A·B·C 재고 집계 보고서

- 저재고 판정 기준: 창고별 행(warehouse row) 수량 < 5 (`low_stock_basis = warehouse_row`)
- 전체 총합(grand_total): **54**

## 창고별 합계

| 창고 | 합계 |
| --- | ---: |
| warehouse-a | 22 |
| warehouse-b | 16 |
| warehouse-c | 16 |
| **합계** | **54** |

## 품목별 총수량

| 품목 | 총수량 |
| --- | ---: |
| mug | 17 |
| bottle | 12 |
| sensor | 11 |
| hub | 13 |
| cable | 1 |

## 저재고 목록

| 창고 | 품목 | 수량 |
| --- | --- | ---: |
| warehouse-a | bottle | 3 |
| warehouse-b | hub | 2 |
| warehouse-c | sensor | 4 |
| warehouse-c | cable | 1 |
