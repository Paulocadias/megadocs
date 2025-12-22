"""
Health check module for system monitoring.
Provides comprehensive health status for production systems.
"""

import os
import psutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Start time for uptime calculation
START_TIME = datetime.now()


def check_database() -> Dict[str, Any]:
    """
    Check database connectivity and integrity.
    
    Returns:
        dict: Database health status
    """
    try:
        db_path = Path("data/stats.db")
        
        if not db_path.exists():
            return {
                "status": "degraded",
                "message": "Database file not found",
                "writable": False
            }
        
        # Test connection
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        
        # Check if writable
        writable = os.access(db_path, os.W_OK)
        
        return {
            "status": "healthy",
            "message": "Database accessible",
            "writable": writable,
            "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database error: {str(e)}",
            "writable": False
        }


def check_disk_space() -> Dict[str, Any]:
    """
    Check available disk space.
    
    Returns:
        dict: Disk space status
    """
    try:
        disk = psutil.disk_usage('/')
        percent_used = disk.percent
        
        # Thresholds
        if percent_used >= 95:
            status = "critical"
        elif percent_used >= 85:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": percent_used
        }
    except Exception as e:
        return {
            "status": "unknown",
            "message": f"Disk check error: {str(e)}"
        }


def check_memory() -> Dict[str, Any]:
    """
    Check system memory usage.
    
    Returns:
        dict: Memory status
    """
    try:
        memory = psutil.virtual_memory()
        percent_used = memory.percent
        
        # Thresholds
        if percent_used >= 90:
            status = "critical"
        elif percent_used >= 75:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_mb": round(memory.total / (1024**2), 2),
            "used_mb": round(memory.used / (1024**2), 2),
            "available_mb": round(memory.available / (1024**2), 2),
            "percent_used": percent_used
        }
    except Exception as e:
        return {
            "status": "unknown",
            "message": f"Memory check error: {str(e)}"
        }


def get_uptime() -> Dict[str, Any]:
    """
    Calculate application uptime.
    
    Returns:
        dict: Uptime information
    """
    try:
        uptime_delta = datetime.now() - START_TIME
        total_seconds = int(uptime_delta.total_seconds())
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return {
            "uptime_seconds": total_seconds,
            "uptime_formatted": f"{days}d {hours}h {minutes}m {seconds}s",
            "started_at": START_TIME.isoformat()
        }
    except Exception as e:
        return {
            "uptime_seconds": 0,
            "message": f"Uptime calculation error: {str(e)}"
        }


def get_health_status() -> Dict[str, Any]:
    """
    Get comprehensive health status of the system.
    
    Returns:
        dict: Complete health check results
    """
    database = check_database()
    disk = check_disk_space()
    memory = check_memory()
    uptime = get_uptime()
    
    # Determine overall status
    statuses = [database.get("status"), disk.get("status"), memory.get("status")]
    
    if "unhealthy" in statuses or "critical" in statuses:
        overall_status = "unhealthy"
    elif "degraded" in statuses or "warning" in statuses:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "uptime": uptime,
        "checks": {
            "database": database,
            "disk": disk,
            "memory": memory
        }
    }
