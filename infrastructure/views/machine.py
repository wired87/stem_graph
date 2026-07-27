# Machine on/off routes: control infrastructure machine state
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


# APIView for POST /api/infrastructure/machine/on/
class MachineOnView(APIView):

    # Turn machine on
    def post(self, request):
        # Placeholder until machine control is implemented
        return Response({'machine': 'on'}, status=status.HTTP_200_OK)


# APIView for POST /api/infrastructure/machine/off/
class MachineOffView(APIView):

    # Turn machine off
    def post(self, request):
        # Placeholder until machine control is implemented
        return Response({'machine': 'off'}, status=status.HTTP_200_OK)
