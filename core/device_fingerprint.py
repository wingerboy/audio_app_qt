import os
import uuid
import json
import hashlib
import platform
import socket
import re
import subprocess

class DeviceFingerprint:
    """
    设备指纹生成器
    生成唯一且稳定的设备标识，即使在软件升级后也不变
    """
    
    @staticmethod
    def get_mac_addresses():
        """获取所有MAC地址"""
        mac_addresses = []
        try:
            # 尝试获取所有网络适配器的MAC地址
            if platform.system() == "Windows":
                # Windows系统
                output = subprocess.check_output('getmac /v /fo csv', shell=True).decode('utf-8')
                for line in output.strip().split('\n')[1:]:  # 跳过标题行
                    parts = line.strip().strip('"').split('","')
                    if len(parts) >= 2:
                        mac = parts[1].replace('-', ':').lower()
                        if re.match(r'^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$', mac):
                            mac_addresses.append(mac)
            
            elif platform.system() == "Darwin":  # macOS
                output = subprocess.check_output('ifconfig', shell=True).decode('utf-8')
                for line in output.split('\n'):
                    if 'ether' in line:
                        mac = line.strip().split('ether ')[1].split(' ')[0].lower()
                        if re.match(r'^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$', mac):
                            mac_addresses.append(mac)
            
            elif platform.system() == "Linux":
                output = subprocess.check_output('ifconfig -a || ip link', shell=True).decode('utf-8')
                for line in output.split('\n'):
                    if 'ether' in line or 'link/ether' in line:
                        parts = line.strip().split()
                        for i, part in enumerate(parts):
                            if part in ['ether', 'link/ether'] and i+1 < len(parts):
                                mac = parts[i+1].lower()
                                if re.match(r'^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$', mac):
                                    mac_addresses.append(mac)
        except:
            # 如果上述方法失败，尝试使用uuid模块获取MAC地址
            try:
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                               for elements in range(0, 2*6, 2)][::-1])
                mac_addresses.append(mac)
            except:
                pass
        
        # 过滤掉虚拟网卡和无效MAC
        filtered_macs = []
        for mac in mac_addresses:
            # 过滤掉全0，全F和虚拟机MAC前缀
            if (not all(c in ['0', ':'] for c in mac) and 
                not all(c in ['f', ':'] for c in mac) and
                not mac.startswith(('00:05:69', '00:0c:29', '00:1c:14', '00:50:56', '00:1c:42'))):
                filtered_macs.append(mac)
        
        return filtered_macs if filtered_macs else mac_addresses
    
    @staticmethod
    def get_cpu_info():
        """获取CPU信息"""
        cpu_info = {
            "processor": platform.processor(),
            "machine": platform.machine()
        }
        
        try:
            if platform.system() == "Windows":
                output = subprocess.check_output('wmic cpu get ProcessorId', shell=True).decode('utf-8')
                for line in output.split('\n'):
                    if line.strip() and not line.strip().startswith("ProcessorId"):
                        cpu_info["processor_id"] = line.strip()
                        break
            elif platform.system() == "Darwin":  # macOS
                output = subprocess.check_output('sysctl -n machdep.cpu.brand_string', shell=True).decode('utf-8')
                cpu_info["brand"] = output.strip()
                output = subprocess.check_output('sysctl -n hw.model', shell=True).decode('utf-8')
                cpu_info["model"] = output.strip()
            elif platform.system() == "Linux":
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('processor'):
                                cpu_info["processor_num"] = line.split(': ')[1].strip()
                            elif line.startswith('model name'):
                                cpu_info["model_name"] = line.split(': ')[1].strip()
                            elif line.startswith('physical id'):
                                cpu_info["physical_id"] = line.split(': ')[1].strip()
                except:
                    pass
        except:
            pass
        
        return cpu_info
    
    @staticmethod
    def get_disk_info():
        """获取磁盘信息"""
        disk_info = {}
        
        try:
            if platform.system() == "Windows":
                output = subprocess.check_output('wmic diskdrive get SerialNumber', shell=True).decode('utf-8')
                serials = []
                for line in output.split('\n'):
                    if line.strip() and not line.strip().startswith("SerialNumber"):
                        serials.append(line.strip())
                disk_info["serial_numbers"] = serials
            elif platform.system() == "Darwin":  # macOS
                output = subprocess.check_output('diskutil info disk0 | grep "Disk / Partition UUID"', shell=True).decode('utf-8')
                if "UUID" in output:
                    disk_info["uuid"] = output.split(': ')[1].strip()
            elif platform.system() == "Linux":
                output = subprocess.check_output('lsblk -d -n -o serial', shell=True).decode('utf-8')
                serials = [s.strip() for s in output.split('\n') if s.strip()]
                if serials:
                    disk_info["serial_numbers"] = serials
        except:
            pass
            
        return disk_info
    
    @staticmethod
    def get_motherboard_info():
        """获取主板信息"""
        mb_info = {}
        
        try:
            if platform.system() == "Windows":
                output = subprocess.check_output('wmic baseboard get SerialNumber', shell=True).decode('utf-8')
                for line in output.split('\n'):
                    if line.strip() and not line.strip().startswith("SerialNumber"):
                        mb_info["serial"] = line.strip()
                        break
            elif platform.system() == "Darwin":  # macOS
                output = subprocess.check_output('system_profiler SPHardwareDataType | grep "Hardware UUID"', shell=True).decode('utf-8')
                if "UUID" in output:
                    mb_info["uuid"] = output.split(': ')[1].strip()
            elif platform.system() == "Linux":
                try:
                    with open('/sys/class/dmi/id/board_serial', 'r') as f:
                        mb_info["serial"] = f.read().strip()
                except:
                    try:
                        output = subprocess.check_output('dmidecode -t 2 | grep Serial', shell=True).decode('utf-8')
                        if "Serial" in output:
                            mb_info["serial"] = output.split(': ')[1].strip()
                    except:
                        pass
        except:
            pass
            
        return mb_info
    
    @staticmethod
    def get_device_fingerprint():
        """获取设备指纹"""
        # 收集硬件信息
        fingerprint_data = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "hostname": socket.gethostname(),
            "mac_addresses": DeviceFingerprint.get_mac_addresses(),
            "cpu_info": DeviceFingerprint.get_cpu_info(),
            "disk_info": DeviceFingerprint.get_disk_info(),
            "motherboard_info": DeviceFingerprint.get_motherboard_info()
        }
        
        # 过滤掉不稳定的信息，确保指纹稳定性
        # 仅使用真正稳定的硬件标识来生成指纹
        stable_data = {
            # 仅保留操作系统类型，去掉版本信息（避免系统更新影响）
            "system": fingerprint_data["system"]
        }
        
        # 主板序列号是最稳定的硬件标识之一
        # 优先使用主板信息，这在大多数电脑上是相对稳定的
        if "serial" in fingerprint_data["motherboard_info"] and fingerprint_data["motherboard_info"]["serial"] not in ["", "0", "INVALID", "To be filled by O.E.M."]:
            stable_data["mb_serial"] = fingerprint_data["motherboard_info"]["serial"]
        elif "uuid" in fingerprint_data["motherboard_info"] and fingerprint_data["motherboard_info"]["uuid"] not in ["", "0", "INVALID"]:
            stable_data["mb_uuid"] = fingerprint_data["motherboard_info"]["uuid"]
        
        # 如果主板信息不可用，尝试使用CPU ID
        if "mb_serial" not in stable_data and "mb_uuid" not in stable_data:
            if "processor_id" in fingerprint_data["cpu_info"]:
                stable_data["cpu_id"] = fingerprint_data["cpu_info"]["processor_id"]
            elif "physical_id" in fingerprint_data["cpu_info"]:
                stable_data["cpu_id"] = fingerprint_data["cpu_info"]["physical_id"]
            # 添加CPU架构信息，这是相对稳定的
            if "machine" in fingerprint_data["cpu_info"]:
                stable_data["cpu_arch"] = fingerprint_data["cpu_info"]["machine"]
        
        # 如果上述硬件标识都不可用，使用磁盘序列号作为备选
        if len(stable_data) <= 1:  # 只有system信息
            if "serial_numbers" in fingerprint_data["disk_info"] and fingerprint_data["disk_info"]["serial_numbers"]:
                # 只选择第一个磁盘的序列号，避免外接磁盘的干扰
                stable_data["disk_serial"] = fingerprint_data["disk_info"]["serial_numbers"][0]
            elif "uuid" in fingerprint_data["disk_info"]:
                stable_data["disk_uuid"] = fingerprint_data["disk_info"]["uuid"]
        
        # 只有在所有硬件标识都不可用的情况下，才考虑使用MAC地址
        # 并且只选择物理网卡的MAC地址（避免虚拟网卡和USB网卡的影响）
        if len(stable_data) <= 1 and fingerprint_data["mac_addresses"]:
            # 只使用第一个物理MAC地址，减少网络变化带来的影响
            stable_data["mac"] = fingerprint_data["mac_addresses"][0]
            
        # 如果以上方法都无法获取稳定的硬件信息，才使用主机名作为最后的备选
        # 通常主机名是相对稳定的，但在某些情况下可能会改变
        if len(stable_data) <= 1:
            stable_data["hostname"] = fingerprint_data["hostname"]
            
        # 添加机器类型标识 (台式机/笔记本/服务器)
        machine_type = DeviceFingerprint._get_machine_type()
        if machine_type:
            stable_data["machine_type"] = machine_type
        
        # 序列化并哈希，使用更强的SHA256算法
        stable_json = json.dumps(stable_data, sort_keys=True)
        fingerprint = hashlib.sha256(stable_json.encode()).hexdigest()
        
        return fingerprint
        
    @staticmethod
    def _get_machine_type():
        """获取机器类型：台式机、笔记本或服务器"""
        try:
            if platform.system() == "Darwin":  # macOS
                output = subprocess.check_output('system_profiler SPHardwareDataType | grep "Model Identifier"', shell=True).decode('utf-8')
                if "MacBook" in output:
                    return "laptop"
                elif "iMac" in output or "Mac mini" in output or "Mac Pro" in output:
                    return "desktop"
            elif platform.system() == "Windows":
                output = subprocess.check_output('wmic computersystem get pcsystemtype', shell=True).decode('utf-8')
                if "1" in output:  # 1 = desktop, 2 = laptop, 3 = workstation, 4 = enterprise server
                    return "desktop"
                elif "2" in output:
                    return "laptop"
                elif "3" in output:
                    return "workstation"
                elif "4" in output:
                    return "server"
            elif platform.system() == "Linux":
                # 检查是否为笔记本电脑
                if os.path.exists("/sys/class/power_supply/BAT0") or os.path.exists("/sys/class/power_supply/BAT1"):
                    return "laptop"
                
                # 尝试使用dmidecode检测系统类型
                try:
                    output = subprocess.check_output('dmidecode -t 3 | grep Type', shell=True).decode('utf-8')
                    if "Desktop" in output:
                        return "desktop"
                    elif "Laptop" in output or "Notebook" in output:
                        return "laptop"
                    elif "Server" in output:
                        return "server"
                except:
                    pass
        except:
            pass
            
        return None
    
    @staticmethod
    def get_device_name():
        """获取设备名称"""
        os_name = platform.system()
        os_version = ""
        
        if os_name == "Windows":
            os_version = platform.version()
        elif os_name == "Darwin":
            os_version = platform.mac_ver()[0]
        elif os_name == "Linux":
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            os_version = line.split('=')[1].strip().strip('"')
                            break
            except:
                os_version = platform.version()
                
        hostname = socket.gethostname()
        return f"{os_name} {os_version} ({hostname})"
    
    @staticmethod
    def get_hardware_info():
        """获取完整硬件信息"""
        cpu_info = DeviceFingerprint.get_cpu_info()
        
        # 获取内存信息
        memory_info = {}
        try:
            if platform.system() == "Windows":
                output = subprocess.check_output('wmic memorychip get capacity', shell=True).decode('utf-8')
                memory_sizes = []
                for line in output.split('\n'):
                    if line.strip() and not line.strip().startswith("Capacity"):
                        try:
                            memory_sizes.append(int(line.strip()))
                        except:
                            pass
                if memory_sizes:
                    memory_info["total"] = sum(memory_sizes)
            elif platform.system() == "Darwin":  # macOS
                output = subprocess.check_output('sysctl hw.memsize', shell=True).decode('utf-8')
                if "hw.memsize" in output:
                    memory_info["total"] = int(output.split(': ')[1].strip())
            elif platform.system() == "Linux":
                try:
                    with open('/proc/meminfo', 'r') as f:
                        for line in f:
                            if line.startswith('MemTotal:'):
                                memory_info["total"] = int(line.split()[1]) * 1024  # KB to bytes
                                break
                except:
                    pass
        except:
            pass
            
        # 构建完整的硬件信息
        hardware_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": DeviceFingerprint.get_disk_info(),
            "motherboard": DeviceFingerprint.get_motherboard_info(),
            "mac_addresses": DeviceFingerprint.get_mac_addresses()
        }
        
        return hardware_info 