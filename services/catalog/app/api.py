from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.catalog import Catalog

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


CatalogDep = Annotated[Catalog, Depends(get_catalog)]


@router.get("/categories")
async def categories(catalog: CatalogDep) -> dict:
    return {"categories": catalog.list_categories()}


@router.get("/categories/{category_id}")
async def category(category_id: str, catalog: CatalogDep) -> dict:
    result = catalog.category(category_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return result


@router.get("/services")
async def services(
    catalog: CatalogDep,
    category: str | None = None,
    search: str | None = None,
) -> dict:
    return {"services": catalog.list_services(category, search)}


@router.get("/services/{service_id}")
async def service(service_id: str, catalog: CatalogDep) -> dict:
    result = catalog.services.get(service_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return result.model_dump()


@router.get("/workflows/{workflow_id}/stages")
async def workflow_stages(workflow_id: str, catalog: CatalogDep) -> dict:
    workflow = _workflow(workflow_id, catalog)
    return {
        "stages": [
            {"id": stage.id, "name": stage.label, "order": stage.order}
            for stage in workflow.stages
        ]
    }


@router.get("/workflows/{workflow_id}")
async def workflow(workflow_id: str, catalog: CatalogDep) -> dict:
    return _workflow(workflow_id, catalog).model_dump()


@router.get("/search")
async def search(
    catalog: CatalogDep, q: Annotated[str, Query(min_length=1, max_length=100)]
) -> dict:
    return {"services": catalog.list_services(search=q)}


def _workflow(workflow_id: str, catalog: Catalog):
    result = catalog.workflows.get(workflow_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return result
