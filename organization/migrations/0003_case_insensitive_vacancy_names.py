from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("organization", "0002_domain_validation_constraints"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="vacancy",
            constraint=models.UniqueConstraint(
                Lower("name"),
                "plan",
                "department",
                name="unique_vacancy_name_ci_per_department_and_plan",
            ),
        ),
    ]
