"""Local, fictional catalog. No credentials or external services required."""
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

ITEMS = [{"id": "1", "name": "Notebook"}, {"id": "2", "name": "Pencil"}]
SPEC = {
    "openapi": "3.0.3", "info": {"title": "Demo catalog", "version": "1.0"},
    "paths": {
        "/items": {
            "get": {"operationId": "list_items", "responses": {"200": {"description": "Items"}}},
            "post": {"operationId": "create_item", "responses": {"200": {"description": "Demo mutation"}}},
        },
        "/items/{item_id}": {"get": {
            "operationId": "get_item",
            "parameters": [{"name": "item_id", "in": "path", "required": True, "schema": {"type": "string"}}],
            "responses": {"200": {"description": "Item"}},
        }},
    },
}

async def spec(request):
    return JSONResponse(SPEC)

async def items(request):
    return JSONResponse(ITEMS)

async def item(request):
    match = next((item for item in ITEMS if item["id"] == request.path_params["item_id"]), None)
    return JSONResponse(match or {"error": "Not found"}, status_code=200 if match else 404)

async def create(request):
    return JSONResponse({"demo": "Write route exists but is excluded by the gateway configuration"})

app = Starlette(routes=[Route("/openapi.json", spec), Route("/items", items),
                       Route("/items", create, methods=["POST"]), Route("/items/{item_id}", item)])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
