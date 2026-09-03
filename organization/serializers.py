from rest_framework import serializers
from organization.models import OrganizationalPlan, OrganizationalUnit, Vacancy


class CompanyInputSerializer(serializers.Serializer):
    company_description = serializers.CharField(
        required=True, 
        allow_blank=False, 
        min_length=10,
        error_messages={
            "required": "La descripción de la empresa es obligatoria.",
            "min_length": "La descripción debe tener al menos 10 caracteres para ser analizada por el agente."
        }
    )


class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        fields = [
            "id", 
            "name", 
            "available_positions", 
            "salary_min", 
            "salary_max", 
            "currency", 
            "description", 
            "required_knowledge"
        ]


class OrganizationalUnitSerializer(serializers.ModelSerializer):
    vacancies = VacancySerializer(many=True, read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationalUnit
        fields = [
            "id", 
            "name", 
            "budget_allocation", 
            "vacancies", 
            "children"
        ]

    def get_children(self, obj):
        return OrganizationalUnitSerializer(obj.children.all(), many=True).data


class OrganizationalPlanSerializer(serializers.ModelSerializer):
    units = serializers.SerializerMethodField()
    vacancies = VacancySerializer(many=True, read_only=True)

    class Meta:
        model = OrganizationalPlan
        fields = [
            "id", 
            "created_at", 
            "raw_response", 
            "assumptions", 
            "units", 
            "vacancies"
        ]

    def get_units(self, obj):
        # Filtra las unidades raíz (sin padre) para estructurar el árbol jerárquico
        root_units = obj.units.filter(parent__isnull=True)
        return OrganizationalUnitSerializer(root_units, many=True).data