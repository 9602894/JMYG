#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import gzip
from urllib.parse import quote

def safe_download(url):
    """安全下载EPG数据"""
    try:
        print(f"📥 下载: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'  # 确保使用utf-8
        return response.text
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

def fix_icon_url(root):
    """对icon的src进行URL编码，避免KU9台标乱码"""
    for channel in root.findall('channel'):
        icon = channel.find('icon')
        if icon is not None and 'src' in icon.attrib:
            original_url = icon.attrib['src']
            # 只对 URL 中非 ASCII 部分进行编码
            parts = original_url.split('/')
            encoded_parts = [quote(p) for p in parts]
            icon.attrib['src'] = '/'.join(encoded_parts)

def fix_display_name(root):
    """确保display-name中文安全"""
    for channel in root.findall('channel'):
        for name in channel.findall('display-name'):
            if name.text:
                name.text = name.text.strip()  # 去掉多余空格
                # KU9一般支持UTF-8，确保为str
                name.text = str(name.text)

def merge_epg_data(cn_content, tw_content):
    """合并两个EPG数据源"""
    print("🔄 合并EPG数据...")
    
    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Merged EPG')
    merged_root.set('source-info-url', 'https://github.com/9602894/JMYG')
    merged_root.set('generator-info-name', 'JMYG EPG Merger')
    
    added_channels = set()
    
    all_content = []
    if cn_content:
        all_content.append(('CN', cn_content))
    if tw_content:
        all_content.append(('TW', tw_content))
    
    for source_name, content in all_content:
        try:
            root = ET.fromstring(content)
            # 修正台标URL和频道名
            fix_icon_url(root)
            fix_display_name(root)
            
            # 添加频道
            for channel in root.findall('channel'):
                channel_id = channel.get('id')
                if channel_id and channel_id not in added_channels:
                    merged_root.append(channel)
                    added_channels.add(channel_id)
            
            # 添加节目
            for programme in root.findall('programme'):
                merged_root.append(programme)
                
            print(f"✅ 已合并 {source_name} 数据")
        except Exception as e:
            print(f"❌ 处理 {source_name} 数据时出错: {e}")
    
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(merged_root, encoding='utf-8').decode()

def simple_timezone_fix(xml_content):
    """简单时区修复"""
    if xml_content:
        return xml_content.replace('+0000', '+0800').replace('UTC', '+0800')
    return xml_content

def save_data(content, filename):
    """保存数据"""
    os.makedirs('epg_data', exist_ok=True)
    
    # 保存XML
    with open(f'epg_data/{filename}', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 保存压缩版
    with gzip.open(f'epg_data/{filename}.gz', 'wt', encoding='utf-8') as f:
        f.write(content)
    
    print(f"💾 已保存: {filename}")

def main():
    print("🚀 开始处理EPG数据...")
    
    # 下载两个数据源
    cn_content = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw_content = safe_download('https://epg.pw/xmltv/epg_TW.xml')
    
    # 时区修复
    cn_content_fixed = simple_timezone_fix(cn_content)
    tw_content_fixed = simple_timezone_fix(tw_content)
    
    # 合并数据
    merged_content = merge_epg_data(cn_content_fixed, tw_content_fixed)
    
    if merged_content:
        save_data(merged_content, 'epg_merged.xml')
        print("✅ EPG数据合并完成！")
    else:
        print("❌ EPG数据合并失败，使用备用方案")
        if cn_content_fixed:
            save_data(cn_content_fixed, 'epg_merged.xml')
        elif tw_content_fixed:
            save_data(tw_content_fixed, 'epg_merged.xml')
    
    print("🎉 EPG处理完成！")

if __name__ == '__main__':
    main()
