from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from file_master.views.gbucket import get_bucket, user_id_from_request, user_prefix
from product.config_creator import get_config, validate_config_values


def input_config_dest(request, session_id: str) -> str:
    """Resolve GCS object path for session config (default: input/<session_id>/config.yaml)."""
    name = (request.data.get('name') or request.data.get('path') or '').strip().lstrip('/')
    if name:
        return name
    return f'input/{session_id}/config.yaml'


# APIView for POST /api/file_master/set-file_master/
class SetFileView(APIView):

    # Upload file_master content or build config.yaml from payload and upsert to input path
    def post(self, request):
        config_values = request.data.get('config')
        if config_values is not None:
            return self._upsert_session_config(request, config_values)

        file_name = request.data.get('name') or request.data.get('file_name', '')
        content = request.data.get('content', '')
        dest_path = f"{user_prefix(request)}{file_name}"
        get_bucket().upload_from_str(dest_path, content)

        return Response(
            {'user_id': user_id_from_request(request), 'name': file_name, 'detail': 'set-file_master'},
            status=status.HTTP_201_CREATED,
        )

    def _upsert_session_config(self, request, config_values: dict) -> Response:
        """Build config.yaml from dynamic fields and upsert under user input prefix."""
        if not isinstance(config_values, dict):
            return Response(
                {'detail': 'config must be an object with StemCNV placeholder values'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session_id = str(request.data.get('session_id', '')).strip()
        if not session_id:
            return Response(
                {'detail': 'session_id is required when posting config'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        missing = validate_config_values(config_values)
        if missing:
            return Response(
                {'detail': 'missing required config fields', 'missing': missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_name = input_config_dest(request, session_id)
        content = get_config(values=config_values)
        dest_path = f"{user_prefix(request)}{file_name}"
        get_bucket().upload_from_str(dest_path, content)
        return Response(
            {
                'user_id': user_id_from_request(request),
                'session_id': session_id,
                'name': file_name,
                'detail': 'set-file_master-config',
            },
            status=status.HTTP_201_CREATED,
        )
