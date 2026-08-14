from django import forms

from organization.domain.exceptions import DomainValidationError
from organization.domain.validators import validate_company_description

COMPANY_DESCRIPTION_HELP = (
    "Para obtener una propuesta mas precisa, incluye el sector, los productos o "
    "servicios, los objetivos, la ubicacion, el tamano esperado y el presupuesto "
    "o capacidad de contratacion. No incluyas datos personales ni confidenciales. "
    "La estructura, las vacantes y los salarios seran estimaciones generadas por IA "
    "y deberan revisarse antes de su publicacion."
)


class CompanyDescriptionForm(forms.Form):
    company_description = forms.CharField(
        label="Describe tu empresa",
        help_text=COMPANY_DESCRIPTION_HELP,
        min_length=80,
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": (
                    "Ejemplo: Somos una empresa de software en Medellin que creara "
                    "una plataforma para pequenas tiendas. Contamos con..."
                ),
                "aria-describedby": "company-description-help company-description-counter",
                "autocomplete": "off",
            }
        ),
    )

    def clean_company_description(self) -> str:
        try:
            return validate_company_description(self.cleaned_data["company_description"])
        except DomainValidationError as exc:
            raise forms.ValidationError(str(exc)) from exc
