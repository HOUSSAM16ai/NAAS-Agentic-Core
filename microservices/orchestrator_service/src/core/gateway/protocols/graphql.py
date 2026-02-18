from fastapi import Request
from fastapi.responses import JSONResponse

from .base import ProtocolAdapter


class GraphQLAdapter(ProtocolAdapter):
    """GraphQL protocol adapter"""

    async def validate_request(self, request: Request) -> tuple[bool, str | None]:
        """Validate GraphQL request"""
        try:
            data = await request.json()
            if not data or "query" not in data:
                return False, "Missing 'query' field in GraphQL request"
            return True, None
        except Exception:
            return False, "Invalid JSON body"

    async def transform_request(self, request: Request) -> dict[str, object]:
        """Transform GraphQL request"""
        data = await request.json()
        return {
            "query": data.get("query"),
            "variables": data.get("variables", {}),
            "operation_name": data.get("operationName"),
            "metadata": {"protocol": "graphql"},
        }

    def transform_response(self, response_data: dict[str, object]) -> dict[str, str | int | bool]:
        """Transform to GraphQL response"""
        return JSONResponse(content={"data": response_data, "errors": None})
