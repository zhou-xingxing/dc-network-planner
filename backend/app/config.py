from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # --- 数据库 ---
    DATABASE_URL: str = "sqlite:///./hcs_lld.db"  # SQLAlchemy 数据库连接地址

    # --- 导入任务 ---
    IMPORT_TTL_MINUTES: int = 30  # 导入临时数据保留时长（分钟），超时后自动清理

    # --- 时区 ---
    APP_TIMEZONE: str = "Asia/Shanghai"  # 应用全局默认时区

    # --- 备份 ---
    BACKUP_DEFAULT_LOCAL_PATH: str = "./backups"  # 本地备份文件默认存放目录
    BACKUP_SCHEDULER_INTERVAL_SECONDS: int = 60  # 备份调度器扫描周期（秒）

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]  # 允许跨域访问的前端地址列表

    # --- JWT 认证 ---
    JWT_SECRET_KEY: str = "change-me-in-production"  # JWT 签名密钥，生产环境必须更换
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # Access Token 有效期（分钟）

    # --- 初始管理员账户（仅首次启动时自动创建） ---
    BOOTSTRAP_ADMIN_USERNAME: str = "admin"  # 初始管理员登录用户名
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin"  # 初始管理员登录密码
    BOOTSTRAP_ADMIN_DISPLAY_NAME: str = "系统管理员"  # 初始管理员显示名称

    model_config = {"env_file": BACKEND_DIR / ".env", "env_file_encoding": "utf-8"}


settings = Settings()
