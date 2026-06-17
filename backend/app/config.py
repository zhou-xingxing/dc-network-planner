from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # --- 数据库 ---
    DATABASE_URL: str = "sqlite:///./dc_network_planner.db"  # SQLAlchemy 数据库连接地址

    # --- 导入任务 ---
    IMPORT_TTL_MINUTES: int = 30  # 导入临时数据保留时长（分钟），超时后自动清理
    IMPORT_CACHE_MAXSIZE: int = 100  # 导入预览缓存最多保留的预览会话数量

    # --- 时区 ---
    APP_TIMEZONE: str = "Asia/Shanghai"  # 应用全局默认时区

    # --- 备份 ---
    BACKUP_DEFAULT_LOCAL_PATH: str = "./backups"  # 本地备份文件默认存放目录
    BACKUP_SCHEDULER_INTERVAL_SECONDS: int = 60  # 备份调度器扫描周期（秒）

    # --- 系统日志 ---
    LOG_LEVEL: str = "INFO"  # 系统日志级别
    LOG_DIR: str = "logs"  # 系统日志目录；相对路径固定到 backend 目录下
    LOG_FILE_NAME: str = "app.log"  # 系统日志主文件名
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 单个日志文件最大字节数
    LOG_BACKUP_COUNT: int = 10  # 轮转日志保留文件数

    # --- 网络地址重叠检测策略（启动后不应变更） ---
    ALLOW_CIDR_OVERLAP_ACROSS_REGIONS: bool = False  # 是否允许 CIDR 跨 Region 重叠
    ALLOW_VLAN_OVERLAP_ACROSS_REGIONS: bool = True  # 是否允许 VLAN 跨 Region 重复

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]  # 允许跨域访问的前端地址列表

    # --- JWT 认证 ---
    JWT_SECRET_KEY: str = "change-me-in-production"  # JWT 签名密钥，生产环境必须更换
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # Access Token 有效期（分钟）

    # --- 初始管理员账户（仅首次启动时自动创建） ---
    BOOTSTRAP_ADMIN_USERNAME: str = "admin"  # 初始管理员登录用户名
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin"  # 初始管理员登录密码

    model_config = {"env_file": BACKEND_DIR / ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
