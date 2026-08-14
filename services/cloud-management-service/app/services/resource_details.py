"""Per-category detail records for a cloud resource: compute, storage,
network, database, and managed Kubernetes."""

from __future__ import annotations

from uuid import UUID

from app.models.resources import (
    CloudCompute,
    CloudDatabase,
    CloudKubernetes,
    CloudNetwork,
    CloudStorage,
)
from app.repositories.resources import (
    CloudComputeRepository,
    CloudDatabaseRepository,
    CloudKubernetesRepository,
    CloudNetworkRepository,
    CloudStorageRepository,
)


class ComputeService:
    def __init__(self, repo: CloudComputeRepository) -> None:
        self._repo = repo

    async def attach(
        self,
        organization_id: UUID,
        *,
        resource_id: UUID,
        instance_type: str | None = None,
        vcpu: int | None = None,
        memory_gb: float | None = None,
        is_spot: bool = False,
        is_reserved: bool = False,
        is_gpu: bool = False,
        image_ref: str | None = None,
    ) -> CloudCompute:
        return await self._repo.create(
            CloudCompute(
                organization_id=organization_id,
                resource_id=resource_id,
                instance_type=instance_type,
                vcpu=vcpu,
                memory_gb=memory_gb,
                is_spot=is_spot,
                is_reserved=is_reserved,
                is_gpu=is_gpu,
                image_ref=image_ref,
            )
        )

    async def record_utilization(
        self, compute: CloudCompute, *, utilization_fraction: float
    ) -> CloudCompute:
        """Record the latest utilization reading supplied by monitoring
        integration (Prompt 044).

        Raises:
            ValueError: If *utilization_fraction* is outside ``[0, 1]``.
        """
        if not 0.0 <= utilization_fraction <= 1.0:
            raise ValueError(
                f"utilization_fraction must be within [0, 1]; got {utilization_fraction}."
            )
        compute.utilization_fraction = utilization_fraction
        return await self._repo.update(compute)


class StorageService:
    def __init__(self, repo: CloudStorageRepository) -> None:
        self._repo = repo

    async def attach(
        self,
        organization_id: UUID,
        *,
        resource_id: UUID,
        storage_class: str | None = None,
        capacity_gb: float | None = None,
        is_encrypted: bool = False,
        is_replicated: bool = False,
    ) -> CloudStorage:
        return await self._repo.create(
            CloudStorage(
                organization_id=organization_id,
                resource_id=resource_id,
                storage_class=storage_class,
                capacity_gb=capacity_gb,
                is_encrypted=is_encrypted,
                is_replicated=is_replicated,
            )
        )


class NetworkService:
    def __init__(self, repo: CloudNetworkRepository) -> None:
        self._repo = repo

    async def attach(
        self,
        organization_id: UUID,
        *,
        resource_id: UUID,
        cidr_block: str | None = None,
        gateway_ref: str | None = None,
    ) -> CloudNetwork:
        return await self._repo.create(
            CloudNetwork(
                organization_id=organization_id,
                resource_id=resource_id,
                cidr_block=cidr_block,
                gateway_ref=gateway_ref,
            )
        )


class DatabaseService:
    def __init__(self, repo: CloudDatabaseRepository) -> None:
        self._repo = repo

    async def attach(
        self,
        organization_id: UUID,
        *,
        resource_id: UUID,
        engine: str,
        engine_version: str | None = None,
        is_high_availability: bool = False,
        storage_gb: float | None = None,
    ) -> CloudDatabase:
        return await self._repo.create(
            CloudDatabase(
                organization_id=organization_id,
                resource_id=resource_id,
                engine=engine,
                engine_version=engine_version,
                is_high_availability=is_high_availability,
                storage_gb=storage_gb,
            )
        )


class KubernetesService:
    def __init__(self, repo: CloudKubernetesRepository) -> None:
        self._repo = repo

    async def attach(
        self,
        organization_id: UUID,
        *,
        resource_id: UUID,
        cluster_reference_id: UUID | None = None,
        node_pool_count: int = 0,
        kubernetes_version: str | None = None,
        autoscaling_enabled: bool = False,
    ) -> CloudKubernetes:
        return await self._repo.create(
            CloudKubernetes(
                organization_id=organization_id,
                resource_id=resource_id,
                cluster_reference_id=cluster_reference_id,
                node_pool_count=node_pool_count,
                kubernetes_version=kubernetes_version,
                autoscaling_enabled=autoscaling_enabled,
            )
        )


__all__ = [
    "ComputeService",
    "DatabaseService",
    "KubernetesService",
    "NetworkService",
    "StorageService",
]
