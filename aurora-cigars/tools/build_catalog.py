#!/usr/bin/env python3
"""生成标准型号目录 content/catalog.csv（价格留空 = 页面显示「请询价」）。

规格为各品牌公开的常规款参数：长度(mm)、环径、出厂型号（vitola de galera）、每盒支数。
限量版、地区限定款不在其中。上架前请对照供应商清单核对盒装支数。
用法：python3 tools/build_catalog.py
"""
import csv
import os

# (品牌, 中文品牌, 浓度, 茄衣, 型号列表)
# 型号：(SKU 后缀, 英文名, 中文名, 出厂型号, 长度, 环径, 每盒支数)
CATALOG = [
    ("Cohiba", "高希霸", "中等至浓郁", "Colorado", [
        ("ROB", "Robustos", "罗布图", "Robusto", 124, 50, 25),
        ("ESP", "Espléndidos", "华美", "Julieta No.2", 178, 47, 25),
        ("LAN", "Lanceros", "长矛", "Laguito No.1", 192, 38, 25),
        ("CEP", "Coronas Especiales", "特级皇冠", "Laguito No.2", 152, 38, 25),
        ("PAN", "Panetelas", "潘纳特拉", "Laguito No.3", 115, 26, 25),
        ("EXQ", "Exquisitos", "优雅", "Seoane", 126, 36, 25),
        ("S1", "Siglo I", "世纪一号", "Perlas", 102, 40, 25),
        ("S2", "Siglo II", "世纪二号", "Mareva", 129, 42, 25),
        ("S3", "Siglo III", "世纪三号", "Corona Grande", 155, 42, 25),
        ("S4", "Siglo IV", "世纪四号", "Corona Gorda", 143, 46, 25),
        ("S5", "Siglo V", "世纪五号", "Dalia", 170, 43, 25),
        ("S6", "Siglo VI", "世纪六号", "Cañonazo", 150, 52, 25),
        ("MSG", "Medio Siglo", "半世纪", "Medio Siglo", 102, 52, 25),
        ("GEN", "Maduro 5 Genios", "马杜罗5 天才", "Genios", 140, 52, 25),
        ("MAG", "Maduro 5 Mágicos", "马杜罗5 魔术", "Mágicos", 115, 52, 25),
        ("SEC", "Maduro 5 Secretos", "马杜罗5 秘密", "Secretos", 110, 40, 25),
        ("B52", "Behike 52", "贝伊可 52", "Laguito No.4", 119, 52, 10),
        ("B54", "Behike 54", "贝伊可 54", "Laguito No.5", 144, 54, 10),
        ("B56", "Behike 56", "贝伊可 56", "Laguito No.6", 166, 56, 10),
    ]),
    ("Montecristo", "蒙特克里斯托", "中等", "Colorado", [
        ("N1", "No.1", "1号", "Cervantes", 165, 42, 25),
        ("N2", "No.2", "2号", "Pirámide", 156, 52, 25),
        ("N3", "No.3", "3号", "Corona", 142, 42, 25),
        ("N4", "No.4", "4号", "Mareva", 129, 42, 25),
        ("N5", "No.5", "5号", "Perlas", 102, 40, 25),
        ("ESP", "Especial", "特制", "Laguito No.1", 192, 38, 25),
        ("ES2", "Especial No.2", "特制2号", "Laguito No.2", 152, 38, 25),
        ("JOY", "Joyitas", "小宝石", "Laguito No.3", 115, 26, 25),
        ("EDM", "Edmundo", "埃德蒙多", "Edmundo", 135, 52, 25),
        ("PED", "Petit Edmundo", "小埃德蒙多", "Petit Edmundo", 110, 52, 25),
        ("DED", "Double Edmundo", "双埃德蒙多", "Doble Edmundo", 155, 50, 25),
        ("MAL", "Línea 1935 Maltés", "1935 马耳他人", "Maltés", 153, 53, 20),
        ("DUM", "Línea 1935 Dumas", "1935 大仲马", "Dumas", 130, 49, 20),
        ("LEY", "Línea 1935 Leyenda", "1935 传奇", "Leyenda", 165, 55, 20),
    ]),
    ("Romeo y Julieta", "罗密欧与朱丽叶", "中等", "Colorado Claro", [
        ("CHU", "Churchills", "丘吉尔", "Julieta No.2", 178, 47, 25),
        ("SCH", "Short Churchills", "短丘吉尔", "Robusto", 124, 50, 25),
        ("WCH", "Wide Churchills", "宽丘吉尔", "Montesco", 130, 55, 25),
        ("PCH", "Petit Churchills", "小丘吉尔", "Petit Robusto", 102, 50, 25),
        ("BEL", "Belicosos", "贝利科索", "Campana", 140, 52, 25),
        ("MFL", "Mille Fleurs", "千花", "Petit Corona", 129, 42, 25),
        ("N2T", "No.2 Tubos", "2号铝管", "Petit Corona", 129, 42, 25),
        ("PJU", "Petit Julietas", "小朱丽叶", "Entreacto", 100, 30, 25),
    ]),
    ("Partagás", "帕特加斯", "浓郁", "Colorado Maduro", [
        ("SD4", "Serie D No.4", "D4", "Robusto", 124, 50, 25),
        ("SD5", "Serie D No.5", "D5", "Petit Robusto", 110, 50, 25),
        ("SE2", "Serie E No.2", "E2", "Duke", 140, 54, 25),
        ("SP2", "Serie P No.2", "P2", "Pirámide", 156, 52, 25),
        ("LUS", "Lusitanias", "卢西塔尼亚", "Prominente", 194, 49, 25),
        ("898", "8-9-8", "8-9-8", "Dalia", 170, 43, 25),
        ("MFL", "Mille Fleurs", "千花", "Petit Corona", 129, 42, 25),
        ("SHO", "Shorts", "短号", "Minuto", 110, 42, 25),
    ]),
    ("H. Upmann", "乌普曼", "中等偏淡", "Claro", [
        ("M46", "Magnum 46", "Magnum 46", "Corona Gorda", 143, 46, 25),
        ("M50", "Magnum 50", "Magnum 50", "Doble", 160, 50, 25),
        ("M54", "Magnum 54", "Magnum 54", "Magnum 54", 120, 54, 25),
        ("N2", "No.2", "2号", "Pirámide", 156, 52, 25),
        ("HC", "Half Corona", "半皇冠", "Half Corona", 90, 44, 25),
        ("CN1", "Connoisseur No.1", "鉴赏家1号", "Hermoso No.4", 127, 48, 25),
        ("SWI", "Sir Winston", "温斯顿爵士", "Julieta No.2", 178, 47, 25),
    ]),
    ("Trinidad", "特立尼达", "中等至浓郁", "Colorado", [
        ("FUN", "Fundadores", "创始人", "Laguito Especial", 192, 40, 24),
        ("REY", "Reyes", "国王", "Reyes", 110, 40, 24),
        ("COL", "Coloniales", "殖民地", "Coloniales", 132, 44, 24),
        ("VIG", "Vigía", "维希亚", "Vigía", 110, 54, 12),
        ("MLU", "Media Luna", "半月", "Media Luna", 115, 50, 12),
        ("ESM", "Esmeralda", "翡翠", "Esmeralda", 145, 53, 12),
        ("TOP", "Topes", "托佩斯", "Topes", 125, 56, 12),
    ]),
    ("Hoyo de Monterrey", "好友", "淡至中等", "Claro", [
        ("EP1", "Epicure No.1", "美食家1号", "Corona Gorda", 143, 46, 25),
        ("EP2", "Epicure No.2", "美食家2号", "Robusto", 124, 50, 25),
        ("EPE", "Epicure Especial", "特制美食家", "Gordito", 141, 50, 25),
        ("DCO", "Double Coronas", "双皇冠", "Prominente", 194, 49, 50),
        ("LHP", "Le Hoyo du Prince", "王子", "Almuerzo", 130, 40, 25),
        ("PRO", "Petit Robustos", "小罗布图", "Petit Robusto", 102, 50, 25),
    ]),
    ("Bolívar", "玻利瓦尔", "浓郁", "Colorado Maduro", [
        ("BFI", "Belicosos Finos", "贝利科索", "Campana", 140, 52, 25),
        ("RCO", "Royal Coronas", "皇家皇冠", "Robusto", 124, 50, 25),
        ("CJU", "Coronas Junior", "少年皇冠", "Minuto", 110, 42, 25),
        ("CGI", "Coronas Gigantes", "巨型皇冠", "Julieta No.2", 178, 47, 25),
        ("PCO", "Petit Coronas", "小皇冠", "Mareva", 129, 42, 25),
    ]),
    ("Punch", "潘趣", "中等至浓郁", "Colorado", [
        ("PUN", "Punch Punch", "潘趣潘趣", "Corona Gorda", 143, 46, 25),
        ("DCO", "Double Coronas", "双皇冠", "Prominente", 194, 49, 25),
        ("PCP", "Petit Coronas del Punch", "小皇冠", "Mareva", 129, 42, 25),
    ]),
]

# Davidoff 为多米尼加产，盒装支数待供应商确认，先留空
DAVIDOFF = [
    ("ASR", "Aniversario Special R", "周年纪念 Special R", "Robusto", 125, 50),
    ("MBR", "Millennium Blend Robusto", "千禧 罗布图", "Robusto", 127, 50),
    ("SN2", "Signature No.2", "签名2号", "Panetela", 152, 38),
]

CODES = {"Cohiba": "COH", "Montecristo": "MON", "Romeo y Julieta": "RYJ", "Partagás": "PAR",
         "H. Upmann": "HUP", "Trinidad": "TRI", "Hoyo de Monterrey": "HDM", "Bolívar": "BOL", "Punch": "PUN"}

HEADER = ["SKU", "中文名", "English Name", "品牌", "价格", "每盒支数", "型号", "长度", "环径", "浓度", "茄衣", "产地"]


def main():
    rows = []
    for brand, brand_cn, strength, wrapper, items in CATALOG:
        for code, en, cn, vitola, length, ring, count in items:
            rows.append([f"{CODES[brand]}-{code}-{count}", f"{brand_cn} {cn}", f"{brand} {en}", brand, "",
                         count, vitola, length, ring, strength, wrapper, "Cuba"])
    for code, en, cn, vitola, length, ring in DAVIDOFF:
        rows.append([f"DAV-{code}", f"大卫杜夫 {cn}", f"Davidoff {en}", "Davidoff", "",
                     "", vitola, length, ring, "中等", "Ecuador Connecticut", "República Dominicana"])
    skus = [r[0] for r in rows]
    assert len(skus) == len(set(skus)), "SKU 重复"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "content", "catalog.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"✓ {len(rows)} 款 → {os.path.normpath(out)}")


if __name__ == "__main__":
    main()
