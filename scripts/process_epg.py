#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import gzip

def safe_download(url):
    """安全下载EPG数据"""
    try:
        print(f"📥 下载: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

def merge_epg_data(cn_content, tw_content):
    """合并两个EPG数据源"""
    print("🔄 合并EPG数据...")
    
    # 创建新的根元素
    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Merged EPG')
    merged_root.set('source-info-url', 'https://github.com/9602894/JMYG')
    merged_root.set('generator-info-name', 'JMYG EPG Merger')
    
    # 用于跟踪已添加的频道，避免重复
    added_channels = set()
    
    # 处理所有内容
    all_content = []
    if cn_content:
        all_content.append(('CN', cn_content))
    if tw_content:
        all_content.append(('TW', tw_content))
    
    for source_name, content in all_content:
        try:
            root = ET.fromstring(content)
            
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
    
    # 转换为XML字符串
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
        # 保存合并的EPG文件
        save_data(merged_content, 'epg_merged.xml')
        print("✅ EPG数据合并完成！")
    else:
        print("❌ EPG数据合并失败，使用备用方案")
        # 备用方案：如果合并失败，至少保存一个可用的
        if cn_content_fixed:
            save_data(cn_content_fixed, 'epg_merged.xml')
        elif tw_content_fixed:
            save_data(tw_content_fixed, 'epg_merged.xml')
    
    print("🎉 EPG处理完成！")

if __name__ == '__main__':
    main()
