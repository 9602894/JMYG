#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
import os
import gzip

def safe_download(url):
    """安全下载 EPG（保持原始字节）"""
    try:
        print(f"📥 下载: {url}")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content   # ⚠️ 必须是 bytes
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

def parse_xml_bytes(xml_bytes):
    """从 bytes 安全解析 XML"""
    try:
        return ET.fromstring(xml_bytes)
    except Exception as e:
        print(f"❌ XML解析失败: {e}")
        return None

def merge_epg_data(cn_bytes, tw_bytes):
    print("🔄 合并 EPG 数据...")

    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Merged EPG')
    merged_root.set('source-info-url', 'https://github.com/9602894/JMYG')
    merged_root.set('generator-info-name', 'JMYG EPG Merger')

    added_channels = set()

    for name, data in [('CN', cn_bytes), ('TW', tw_bytes)]:
        if not data:
            continue

        root = parse_xml_bytes(data)
        if root is None:
            continue

        for ch in root.findall('channel'):
            cid = ch.get('id')
            if cid and cid not in added_channels:
                merged_root.append(ch)
                added_channels.add(cid)

        for p in root.findall('programme'):
            merged_root.append(p)

        print(f"✅ 已合并 {name}")

    # ⚠️ 输出为 bytes
    xml_bytes = ET.tostring(
        merged_root,
        encoding='utf-8',
        xml_declaration=True
    )

    return xml_bytes

def save_data(xml_bytes, filename):
    os.makedirs('epg_data', exist_ok=True)

    xml_path = f'epg_data/{filename}'
    gz_path = f'{xml_path}.gz'

    # 保存 XML（binary）
    with open(xml_path, 'wb') as f:
        f.write(xml_bytes)

    # 保存 gzip（binary）
    with gzip.open(gz_path, 'wb') as f:
        f.write(xml_bytes)

    print(f"💾 已保存: {xml_path}")
    print(f"💾 已保存: {gz_path}")

def main():
    print("🚀 开始处理 EPG 数据")

    cn = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw = safe_download('https://epg.pw/xmltv/epg_TW.xml')

    merged = merge_epg_data(cn, tw)

    if merged:
        save_data(merged, 'epg_merged.xml')
        print("✅ 合并完成，无乱码")
    else:
        print("❌ 合并失败")

if __name__ == '__main__':
    main()
