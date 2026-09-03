from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from organization.bootstrap import build_generation_service
from organization.domain.exceptions import GenerationError
from organization.serializers import CompanyInputSerializer, OrganizationalPlanSerializer

class GenerateOrganizationAPIView(APIView):
    def post(self, request):
        serializer = CompanyInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            plan = build_generation_service().execute(serializer.validated_data["company_description"])
        except GenerationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        
        response_serializer = OrganizationalPlanSerializer(plan)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)