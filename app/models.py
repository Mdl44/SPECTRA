
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import CIDR, INET, MACADDR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "device"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(unique=True)
    management_ip: Mapped[str] = mapped_column(INET, unique=True)
    device_type: Mapped[str]
    vendor: Mapped[str | None]
    model: Mapped[str | None]
    serial_number: Mapped[str | None]
    os_version: Mapped[str | None]
    role: Mapped[str | None]
    driver: Mapped[str | None]
    location: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Discovery(Base):
    __tablename__ = "discovery"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed_device_id: Mapped[int | None] = mapped_column(ForeignKey("device.id", ondelete="SET NULL"))
    method: Mapped[str]
    status: Mapped[str] = mapped_column(default="running")
    devices_found: Mapped[int] = mapped_column(default=0)
    devices_new: Mapped[int] = mapped_column(default=0)
    devices_known: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None]
    log: Mapped[str | None]


class IpamSubnet(Base):
    __tablename__ = "ipam_subnet"

    id: Mapped[int] = mapped_column(primary_key=True)
    network: Mapped[str] = mapped_column(CIDR, unique=True)
    name: Mapped[str | None]
    gateway: Mapped[str | None] = mapped_column(INET)
    vlan_id: Mapped[int | None]
    description: Mapped[str | None]


class IpamAddress(Base):
    __tablename__ = "ipam_address"

    id: Mapped[int] = mapped_column(primary_key=True)
    subnet_id: Mapped[int] = mapped_column(ForeignKey("ipam_subnet.id", ondelete="CASCADE"))
    ip_address: Mapped[str] = mapped_column(INET, unique=True)
    hostname: Mapped[str | None]
    mac_address: Mapped[str | None] = mapped_column(MACADDR)
    interface_id: Mapped[int | None] = mapped_column(ForeignKey("interface.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(default="active")
    last_seen: Mapped[datetime] = mapped_column(server_default=func.now())


class UnregisteredHost(Base):
    __tablename__ = "unregistered_host"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_address: Mapped[str] = mapped_column(INET, unique=True)
    mac_address: Mapped[str | None] = mapped_column(MACADDR)
    hostname: Mapped[str | None]
    discovered_by: Mapped[str | None]
    first_seen: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(server_default=func.now())


class Config(Base):
    __tablename__ = "config"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id", ondelete="RESTRICT"))
    config_type: Mapped[str] = mapped_column(default="running")
    config_text: Mapped[str]
    config_hash: Mapped[str]
    collected_at: Mapped[datetime] = mapped_column(server_default=func.now())
    diff_text: Mapped[str | None]
    is_acknowledged: Mapped[bool] = mapped_column(default=False)


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("device.id", ondelete="SET NULL"))
    severity: Mapped[str]
    category: Mapped[str]
    message: Mapped[str]
    is_resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
