from django import forms
from django.utils.translation import gettext_lazy as _

from organization.domain.exceptions import DomainValidationError
from organization.domain.validators import (
    MAX_DESCRIPTION_LENGTH,
    MIN_DESCRIPTION_LENGTH,
    validate_company_description,
)

COMPANY_DESCRIPTION_HELP = _(
    "Para obtener una propuesta mas precisa, incluye el sector, los productos o "
    "servicios, los objetivos, la ubicacion, el tamano esperado y el presupuesto "
    "o capacidad de contratacion. No incluyas datos personales ni confidenciales. "
    "La estructura, las vacantes y los salarios seran estimaciones generadas por IA "
    "y deberan revisarse antes de su publicacion."
)


class CompanyDescriptionForm(forms.Form):
    company_description = forms.CharField(
        label=_("Describe tu empresa"),
        help_text=COMPANY_DESCRIPTION_HELP,
        min_length=MIN_DESCRIPTION_LENGTH,
        max_length=MAX_DESCRIPTION_LENGTH,
        error_messages={
            "required": _("La descripción de la empresa es obligatoria."),
            "min_length": _("Describe la empresa con al menos %(limit_value)d caracteres."),
            "max_length": _("La descripción no puede superar %(limit_value)d caracteres."),
        },
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": _(
                    "Ejemplo: Somos una empresa de software en Medellin que creara "
                    "una plataforma para pequenas tiendas. Contamos con..."
                ),
                "aria-describedby": "company-description-help company-description-counter",
                "autocomplete": "off",
                "minlength": MIN_DESCRIPTION_LENGTH,
                "maxlength": MAX_DESCRIPTION_LENGTH,
                "required": True,
                "data-min-length": MIN_DESCRIPTION_LENGTH,
            }
        ),
    )

    def clean_company_description(self) -> str:
        try:
            return validate_company_description(self.cleaned_data["company_description"])
        except DomainValidationError as exc:
            raise forms.ValidationError(str(exc)) from exc


class ReportRequestForm(forms.Form):
    FORMAT_CHOICES = (("csv", _("CSV (Excel)")), ("json", _("JSON")))

    format = forms.ChoiceField(
        label=_("Formato del reporte"),
        choices=FORMAT_CHOICES,
        initial="csv",
        widget=forms.RadioSelect,
    )
