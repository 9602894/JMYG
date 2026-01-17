#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
import os
import gzip

UTF8_BOM = b'\xef\xbb\xbf'

def safe_download(url):
    try:
        print(f"📥 下载: {url}")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

def parse_xml_bytes(data):
    try:
        return ET.fromstring(data)
    except Exception as e:
        print(f"❌ XML解析失败: {e}")
        return None

def merge_epg_data(cn_bytes, tw_bytes):
    print("🔄 合并 EPG 数据...")

    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Ku9 UTF8-BOM EPG')
    merged_root.set('generator-info-name', 'JMYG')

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

    xml_body = ET.tostring(
        merged_root,
        encoding='utf-8',
        xml_declaration=True
    )

    # ⚠️ 关键：加 UTF-8 BOM
    return UTF8_BOM + xml_body

def save_data(xml_bytes, filename):
    os.makedirs('epg_data', exist_ok=True)

    xml_path = f'epg_data/{filename}'
    gz_path = f'{xml_path}.gz'

    with open(xml_path, 'wb') as f:
        f.write(xml_bytes)

    with gzip.open(gz_path, 'wb') as f:
        f.write(xml_bytes)

    print(f"💾 已保存: {xml_path}")
    print(f"💾 已保存: {gz_path}")

def main():
    print("🚀 开始生成 Ku9 专用 EPG")

    cn = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw = safe_download('https://epg.pw/xmltv/epg_TW.xml')

    merged = merge_epg_data(cn, tw)

    if merged:
        save_data(merged, 'epg_ku9.xml')
        print("✅ Ku9 解析不会乱码")
    else:
        print("❌ 生成失败")

if __name__ == '__main__':
    main()
