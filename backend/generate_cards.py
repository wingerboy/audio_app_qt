#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成卡密工具

功能：批量生成卡密记录，写入数据库与本地文件

要求：
1. 卡密的card_id是英文字母+数字的形式，长度为8位
   - 字母数字各4位
   - 第一位必须为字母
   - 可以指定前缀，如test0000，如不指定则随机生成
2. 可以指定生成卡密的数量
3. 卡密的card_key为全字母的形式，长度限制为16
4. 可以指定max_device_count数量，默认为3
5. 有效期(validity_days)可配置，默认30天
6. 生成卡密同时写入本地文件和MySQL数据库

使用方法：
    python generate_cards.py -n 5 -p TEST -t test -d 30 -m 3 -o cards.txt
"""

import os
import sys
import argparse
import random
import string
import datetime
import pymysql
from pymysql.cursors import DictCursor
import csv

# 数据库连接配置，与app.py保持一致
DB_CONFIG = {
    'host': 'obmt6nn1aqdr2nb4-mi.aliyun-cn-hangzhou-internet.oceanbase.cloud',
    'port': 3306,
    'user': 'wingerboy',
    'password': 'LIUyawen__12',
    'db': 'audio_app_offline',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)

def generate_card_id(prefix=None):
    """
    生成卡密ID
    
    Args:
        prefix: 指定前缀
    
    Returns:
        生成的卡密ID, 格式为: 字母(4位) + 数字(4位)
    """
    # 处理前缀
    if prefix:
        # 确保前缀是字母并且长度不超过4位
        prefix = ''.join(c for c in prefix if c.isalpha()).upper()
        prefix = prefix[:4]
        
        # 补齐字母部分到4位
        if len(prefix) < 4:
            remaining_letters = 4 - len(prefix)
            prefix += ''.join(random.choices(string.ascii_uppercase, k=remaining_letters))
    else:
        # 随机生成4位字母
        prefix = ''.join(random.choices(string.ascii_uppercase, k=4))
    
    # 生成4位数字
    numbers = ''.join(random.choices(string.digits, k=4))
    
    return prefix + numbers

def generate_card_key():
    """
    生成卡密密钥
    
    Returns:
        16位全字母密钥
    """
    return ''.join(random.choices(string.ascii_letters, k=16))

def generate_cards(count, prefix=None, user_type="standard", validity_days=30, max_device_count=3, output_file=None):
    """
    批量生成卡密
    
    Args:
        count: 生成数量
        prefix: 卡密ID前缀
        user_type: 用户类型 standard/premium
        validity_days: 有效期(天)
        max_device_count: 最大设备数
        output_file: 输出文件名
    
    Returns:
        生成的卡密列表
    """
    # 验证参数
    if count <= 0:
        raise ValueError("生成数量必须大于0")
    
    if user_type not in ["standard", "premium"]:
        raise ValueError("用户类型必须是standard或premium")
    
    # 连接数据库
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 准备生成的卡密列表
        generated_cards = []
        now = datetime.datetime.now()
        
        # 开始生成卡密
        for _ in range(count):
            # 生成卡密ID，确保唯一
            while True:
                card_id = generate_card_id(prefix)
                # 检查卡密ID是否已存在
                cursor.execute("SELECT card_id FROM card_keys WHERE card_id = %s", (card_id,))
                if not cursor.fetchone():
                    break
            
            # 生成卡密密钥
            card_key = generate_card_key()
            
            # 构造卡密记录
            card_data = {
                'card_id': card_id,
                'card_key': card_key,
                'user_type': user_type,
                'status': 'inactive',
                'max_device_count': max_device_count,
                'device_count': 0,
                'validity_days': validity_days,
                'created_at': now,
                'activated_at': None,
                'expiry_date': None,
                'last_login_at': None
            }
            
            # 插入数据库
            cursor.execute('''
            INSERT INTO card_keys (card_id, card_key, user_type, status, max_device_count, 
                                  device_count, validity_days, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                card_data['card_id'],
                card_data['card_key'],
                card_data['user_type'],
                card_data['status'],
                card_data['max_device_count'],
                card_data['device_count'],
                card_data['validity_days'],
                card_data['created_at']
            ))
            
            # 添加到结果列表
            generated_cards.append(card_data)
            
            print(f"已生成卡密: {card_id} / {card_key}")
        
        # 提交事务
        conn.commit()
        
        # 如果指定了输出文件，则将卡密写入文件
        if output_file:
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['card_id', 'card_key', 'user_type', 'max_device_count', 'validity_days', 'created_at'])
                
                # 写入卡密数据
                for card in generated_cards:
                    writer.writerow([
                        card['card_id'],
                        card['card_key'],
                        card['user_type'],
                        card['max_device_count'],
                        card['validity_days'],
                        card['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    ])
            
            print(f"卡密已保存到文件: {output_file}")
        
        # 返回生成的卡密列表
        return generated_cards
    
    except Exception as e:
        # 发生错误时回滚事务
        conn.rollback()
        print(f"生成卡密出错: {str(e)}")
        raise e
    
    finally:
        # 关闭数据库连接
        cursor.close()
        conn.close()

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='批量生成卡密工具')
    parser.add_argument('-n', '--number', type=int, required=True, help='生成卡密数量')
    parser.add_argument('-p', '--prefix', type=str, help='卡密ID前缀，如TEST')
    parser.add_argument('-t', '--type', type=str, default='standard', choices=['standard', 'premium', 'test'], help='用户类型: standard或premium')
    parser.add_argument('-d', '--days', type=int, default=30, help='卡密有效期(天数)，默认30天')
    parser.add_argument('-m', '--max-devices', type=int, default=3, help='最大设备数，默认3台')
    parser.add_argument('-o', '--output', type=str, default='cards.csv', help='输出文件名，默认cards.csv')
    
    args = parser.parse_args()
    
    try:
        # 生成卡密
        cards = generate_cards(
            count=args.number,
            prefix=args.prefix,
            user_type=args.type,
            validity_days=args.days,
            max_device_count=args.max_devices,
            output_file=args.output
        )
        
        print(f"成功生成 {len(cards)} 个卡密")
    
    except Exception as e:
        print(f"生成卡密失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 