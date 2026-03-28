"""Security search, field search, and field info tool handlers."""

import json

from bloomberg_mcp.server import mcp
from bloomberg_mcp.models import SearchSecuritiesInput, SearchFieldsInput, FieldInfoInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response


@mcp.tool(
    name="bloomberg_search_securities",
    annotations={
        "title": "Search Securities",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_search_securities(params: SearchSecuritiesInput) -> str:
    """
    Search for securities by name, ticker, or description.

    Use this to find the correct Bloomberg identifier for a security
    before fetching data. Returns security identifiers and descriptions.

    Args:
        params: SearchSecuritiesInput containing query and filters

    Returns:
        List of matching securities with their Bloomberg identifiers

    Example:
        query="Apple", yellow_key="Equity"
    """
    try:
        from bloomberg_mcp.tools import search_securities

        results = search_securities(
            query=params.query,
            max_results=params.max_results,
            yellow_key=params.yellow_key
        )

        if not results:
            return f"No securities found matching '{params.query}'"

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"## Security Search: '{params.query}'", ""]
            for r in results:
                lines.append(f"- **{r.get('security', 'N/A')}**: {r.get('description', 'N/A')}")
            result = "\n".join(lines)
        else:
            result = json.dumps(results, indent=2)

        return _truncate_response(result)

    except Exception as e:
        return f"Error searching securities: {str(e)}"


@mcp.tool(
    name="bloomberg_search_fields",
    annotations={
        "title": "Search Fields",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_search_fields(params: SearchFieldsInput) -> str:
    """
    Search for Bloomberg field mnemonics by keyword.

    Bloomberg has 30,000+ fields. Use this tool to discover the correct
    field mnemonic for the data you need. Always search before assuming
    a field name.

    Args:
        params: SearchFieldsInput containing search query and filters

    Returns:
        List of matching fields with IDs and descriptions

    Example:
        query="price earnings growth" -> finds PEG_RATIO
        query="dividend yield" -> finds DIVIDEND_YIELD, etc.
    """
    try:
        from bloomberg_mcp.tools import search_fields

        results = search_fields(
            query=params.query,
            field_type=params.field_type
        )

        # Limit results
        results = results[:params.max_results]

        if not results:
            return f"No fields found matching '{params.query}'"

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"## Field Search: '{params.query}'", ""]
            for r in results:
                lines.append(f"- **{r.get('id', 'N/A')}**: {r.get('description', 'N/A')}")
            result = "\n".join(lines)
        else:
            result = json.dumps(results, indent=2)

        return _truncate_response(result)

    except Exception as e:
        return f"Error searching fields: {str(e)}"


@mcp.tool(
    name="bloomberg_get_field_info",
    annotations={
        "title": "Get Field Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_field_info(params: FieldInfoInput) -> str:
    """
    Get detailed metadata about specific Bloomberg fields.

    Returns documentation, data types, and usage information for
    the specified field mnemonics.

    Args:
        params: FieldInfoInput containing field IDs to look up

    Returns:
        Detailed field information including data type and documentation

    Example:
        field_ids=["PX_LAST", "PE_RATIO"]
    """
    try:
        from bloomberg_mcp.tools import get_field_info

        results = get_field_info(
            field_ids=params.field_ids,
            return_documentation=params.return_documentation
        )

        if not results:
            return f"No field information found for: {params.field_ids}"

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["## Field Information", ""]
            for f in results:
                lines.append(f"### {f.get('id', 'N/A')}")
                lines.append(f"- **Description**: {f.get('description', 'N/A')}")
                if f.get('datatype'):
                    lines.append(f"- **Data Type**: {f.get('datatype')}")
                if f.get('categoryName'):
                    lines.append(f"- **Category**: {f.get('categoryName')}")
                if f.get('documentation'):
                    lines.append(f"- **Documentation**: {f.get('documentation')}")
                lines.append("")
            result = "\n".join(lines)
        else:
            result = json.dumps(results, indent=2)

        return _truncate_response(result)

    except Exception as e:
        return f"Error fetching field info: {str(e)}"
